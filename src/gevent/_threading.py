"""A clone of threading module (version 2.7.2) that always
targets real OS threads. (Unlike 'threading' which flips between
green and OS threads based on whether the monkey patching is in effect
or not).

This module is missing 'Thread' class, but includes 'Queue'.
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

        # If the lock defines _release_save() and/or _acquire_restore(),
        # these override the default implementations (which just call
        # release() and acquire() on the lock).  Ditto for _is_owned().
        try:
            self._release_save = lock._release_save
        except AttributeError:
            pass
        try:
            self._acquire_restore = lock._acquire_restore
        except AttributeError:
            pass
        try:
            self._is_owned = lock._is_owned
        except AttributeError:
            pass

    def __enter__(self):
        return self.__lock.__enter__()

    def __exit__(self, t, v, tb):
        return self.__lock.__exit__(t, v, tb)

    def __repr__(self):
        return "<Condition(%s, %d)>" % (self.__lock, len(self.__waiters))

    def _release_save(self):
        self.__lock.release()           # No state to save

    def _acquire_restore(self, x): # pylint:disable=unused-argument
        self.__lock.acquire()           # Ignore saved state

    def _is_owned(self):
        # Return True if lock is owned by current_thread.
        # This method is called only if __lock doesn't have _is_owned().
        if self.__lock.acquire(0):
            self.__lock.release()
            return False
        return True

    def wait(self):
        # The condition MUST be owned, but we don't check that.
        waiter = Lock()
        waiter.acquire()
        self.__waiters.append(waiter)
        saved_state = self._release_save()
        try:    # restore state no matter what (e.g., KeyboardInterrupt)
            waiter.acquire() # Block on the native lock
        finally:
            self._acquire_restore(saved_state)

    def notify_one(self):
        # The condition MUST be owned, but we don't check that.
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
        with self._not_empty:
            self._queue.append(item)
            self.unfinished_tasks += 1
            self._not_empty.notify_one()

    def get(self):
        """Remove and return an item from the queue.
        """
        with self._not_empty:
            while not self._queue:
                self._not_empty.wait()
            item = self._queue.popleft()
            return item
