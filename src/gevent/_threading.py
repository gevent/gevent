"""
A small selection of primitives that always work with
native threads. This has very limited utility and is
targeted only for the use of gevent's threadpool.
"""
from __future__ import absolute_import

from collections import deque

from gevent import monkey
from gevent._compat import thread_mod_name


__all__ = [
    'Lock',
    'Queue',
]


start_new_thread, Lock, get_thread_ident, = monkey.get_original(thread_mod_name, [
    'start_new_thread', 'allocate_lock', 'get_ident',
])


class _Condition(object):
    # pylint:disable=method-hidden

    __slots__ = (
        '_lock',
        '_waiters',
    )

    def __init__(self, lock):
        self._lock = lock
        self._waiters = []

        # No need to special case for _release_save and
        # _acquire_restore; those are only used for RLock, and
        # we don't use those.

    def __enter__(self):
        return self._lock.__enter__()

    def __exit__(self, t, v, tb):
        return self._lock.__exit__(t, v, tb)

    def __repr__(self):
        return "<Condition(%s, %d)>" % (self._lock, len(self._waiters))

    def wait(self, wait_lock):
        # TODO: It would be good to support timeouts here so that we can
        # let idle threadpool threads die. Under Python 3, ``Lock.acquire``
        # has that ability, but Python 2 doesn't expose that. We could use
        # libuv's ``uv_cond_wait`` to implement this whole class and get timeouts
        # everywhere.

        # This variable is for the monitoring utils to know that
        # this is an idle frame and shouldn't be counted.
        gevent_threadpool_worker_idle = True # pylint:disable=unused-variable

        # Our ``_lock`` MUST be owned, but we don't check that.
        # The ``wait_lock`` must be *un*owned.
        wait_lock.acquire()
        self._waiters.append(wait_lock)
        self._lock.release()

        try:
            wait_lock.acquire() # Block on the native lock
        finally:
            self._lock.acquire()

        wait_lock.release()

    def notify_one(self):
        # The lock SHOULD be owned, but we don't check that.
        try:
            waiter = self._waiters.pop()
        except IndexError:
            # Nobody around
            pass
        else:
            # The owner of the ``waiter`` is blocked on
            # acquiring it again, so when we ``release`` it, it
            # is free to be scheduled and resume.
            waiter.release()


class Queue(object):
    """Create a queue object.

    The queue is always infinite size.
    """

    __slots__ = ('_queue', '_mutex', '_not_empty', 'unfinished_tasks')

    def __init__(self):
        self._queue = deque()
        # mutex must be held whenever the queue is mutating.  All methods
        # that acquire mutex must release it before returning.  mutex
        # is shared between the three conditions, so acquiring and
        # releasing the conditions also acquires and releases mutex.
        self._mutex = Lock()
        # Notify not_empty whenever an item is added to the queue; a
        # thread waiting to get is notified then.
        self._not_empty = _Condition(self._mutex)

        self.unfinished_tasks = 0

    def task_done(self):
        """Indicate that a formerly enqueued task is complete.

        Used by Queue consumer threads.  For each get() used to fetch a task,
        a subsequent call to task_done() tells the queue that the processing
        on the task is complete.

        If a join() is currently blocking, it will resume when all items
        have been processed (meaning that a task_done() call was received
        for every item that had been put() into the queue).

        Raises a ValueError if called more times than there were items
        placed in the queue.
        """
        with self._mutex:
            unfinished = self.unfinished_tasks - 1
            if unfinished <= 0:
                if unfinished < 0:
                    raise ValueError('task_done() called too many times')
            self.unfinished_tasks = unfinished

    def qsize(self, len=len):
        """Return the approximate size of the queue (not reliable!)."""
        return len(self._queue)

    def empty(self):
        """Return True if the queue is empty, False otherwise (not reliable!)."""
        return not self.qsize()

    def full(self):
        """Return True if the queue is full, False otherwise (not reliable!)."""
        return False

    def put(self, item):
        """Put an item into the queue.
        """
        with self._mutex:
            self._queue.append(item)
            self.unfinished_tasks += 1
            self._not_empty.notify_one()

    def get(self, cookie):
        """Remove and return an item from the queue.
        """
        with self._mutex:
            while not self._queue:
                # Temporarily release our mutex and wait for someone
                # to wake us up. There *should* be an item in the queue
                # after that.
                self._not_empty.wait(cookie)
            item = self._queue.popleft()
            return item

    def allocate_cookie(self):
        """
        Create and return the *cookie* to pass to `get()`.

        Each thread that will use `get` needs a distinct cookie.
        """
        return Lock()

    def kill(self):
        """
        Call to destroy this object.

        Use this when it's not possible to safely drain the queue, e.g.,
        after a fork when the locks are in an uncertain state.
        """
        self._queue = None
        self._mutex = None
        self._not_empty = None
        self.unfinished_tasks = None
