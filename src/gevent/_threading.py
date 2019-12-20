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


# pylint 2.0.dev2 things collections.dequeue.popleft() doesn't return
# pylint:disable=assignment-from-no-return

class _Condition(object):
    # pylint:disable=method-hidden

    def __init__(self, lock):
        self.__lock = lock
        self.__waiters = []

        # No need to special case for _release_save and
        # _acquire_restore; those are only used for RLock, and
        # we don't use those.

    def __enter__(self):
        return self.__lock.__enter__()

    def __exit__(self, t, v, tb):
        return self.__lock.__exit__(t, v, tb)

    def __repr__(self):
        return "<Condition(%s, %d)>" % (self.__lock, len(self.__waiters))

    def wait(self):
        # This variable is for the monitoring utils to know that
        # this is an idle frame and shouldn't be counted.
        gevent_threadpool_worker_idle = True # pylint:disable=unused-variable

        # Our __lock MUST be owned, but we don't check that.
        waiter = Lock()
        waiter.acquire()
        self.__waiters.append(waiter)
        self.__lock.release()

        try:
            waiter.acquire() # Block on the native lock
        finally:
            self.__lock.acquire()

        # just good form to release the lock we're holding before it goes
        # out of scope
        waiter.release()

    def notify_one(self):
        # The lock SHOULD be owned, but we don't check that.
        try:
            waiter = self.__waiters.pop()
        except IndexError:
            # Nobody around
            pass
        else:
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

    def get(self):
        """Remove and return an item from the queue.
        """
        with self._mutex:
            while not self._queue:
                self._not_empty.wait()
            item = self._queue.popleft()
            return item

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
