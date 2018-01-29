"""A clone of threading module (version 2.7.2) that always
targets real OS threads. (Unlike 'threading' which flips between
green and OS threads based on whether the monkey patching is in effect
or not).

This module is missing 'Thread' class, but includes 'Queue'.
"""
from __future__ import absolute_import

from collections import deque
from itertools import islice as _islice

from gevent import monkey
from gevent._compat import PY3


__all__ = [
    'Condition',
    'Lock',
    'Queue',
]


thread_name = '_thread' if PY3 else 'thread'
start_new_thread, Lock, = monkey.get_original(thread_name, [
    'start_new_thread', 'allocate_lock',
])


class Condition(object):
    # pylint:disable=method-hidden

    def __init__(self, lock):
        self.__lock = lock
        # Export the lock's acquire() and release() methods
        self.acquire = lock.acquire
        self.release = lock.release
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
        self.__waiters = []

    def __enter__(self):
        return self.__lock.__enter__()

    def __exit__(self, *args):
        return self.__lock.__exit__(*args)

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
        if not self._is_owned():
            raise RuntimeError("cannot wait on un-acquired lock")
        waiter = Lock()
        waiter.acquire()
        self.__waiters.append(waiter)
        saved_state = self._release_save()
        try:    # restore state no matter what (e.g., KeyboardInterrupt)
            waiter.acquire()
        finally:
            self._acquire_restore(saved_state)

    def notify(self, n=1):
        if not self._is_owned():
            raise RuntimeError("cannot notify on un-acquired lock")
        all_waiters = self.__waiters
        waiters_to_notify = deque(_islice(all_waiters, n))
        if not waiters_to_notify:
            return
        for waiter in waiters_to_notify:
            waiter.release()
            try:
                all_waiters.remove(waiter)
            except ValueError:
                pass


class Queue(object):
    """Create a queue object.

    The queue is always infinite size.
    """


    def __init__(self):
        self.queue = deque()
        # mutex must be held whenever the queue is mutating.  All methods
        # that acquire mutex must release it before returning.  mutex
        # is shared between the three conditions, so acquiring and
        # releasing the conditions also acquires and releases mutex.
        self.mutex = Lock()
        # Notify not_empty whenever an item is added to the queue; a
        # thread waiting to get is notified then.
        self.not_empty = Condition(self.mutex)

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
        with self.mutex:
            unfinished = self.unfinished_tasks - 1
            if unfinished <= 0:
                if unfinished < 0:
                    raise ValueError('task_done() called too many times')
            self.unfinished_tasks = unfinished

    def qsize(self, len=len):
        """Return the approximate size of the queue (not reliable!)."""
        with self.mutex:
            return len(self.queue)

    def empty(self):
        """Return True if the queue is empty, False otherwise (not reliable!)."""
        return not self.qsize()

    def full(self):
        """Return True if the queue is full, False otherwise (not reliable!)."""
        return False

    def put(self, item):
        """Put an item into the queue.
        """
        with self.mutex:
            self.queue.append(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def get(self):
        """Remove and return an item from the queue.
        """
        with self.mutex:
            while not self.queue:
                self.not_empty.wait()
            item = self.queue.popleft()
            return item
