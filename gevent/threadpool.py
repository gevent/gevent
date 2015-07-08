# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
from __future__ import absolute_import
import sys
import os
from gevent.hub import get_hub, getcurrent, sleep, integer_types
from gevent.event import AsyncResult
from gevent.greenlet import Greenlet
from gevent.pool import GroupMappingMixin
from gevent.lock import Semaphore
from gevent._threading import Lock, Queue, start_new_thread


__all__ = ['ThreadPool',
           'ThreadResult']


class ThreadPool(GroupMappingMixin):

    def __init__(self, maxsize, hub=None):
        if hub is None:
            hub = get_hub()
        self.hub = hub
        self._maxsize = 0
        self.manager = None
        self.pid = os.getpid()
        self.fork_watcher = hub.loop.fork(ref=False)
        self._init(maxsize)

    def _set_maxsize(self, maxsize):
        if not isinstance(maxsize, integer_types):
            raise TypeError('maxsize must be integer: %r' % (maxsize, ))
        if maxsize < 0:
            raise ValueError('maxsize must not be negative: %r' % (maxsize, ))
        difference = maxsize - self._maxsize
        self._semaphore.counter += difference
        self._maxsize = maxsize
        self.adjust()
        # make sure all currently blocking spawn() start unlocking if maxsize increased
        self._semaphore._start_notify()

    def _get_maxsize(self):
        return self._maxsize

    maxsize = property(_get_maxsize, _set_maxsize)

    def __repr__(self):
        return '<%s at 0x%x %s/%s/%s>' % (self.__class__.__name__, id(self), len(self), self.size, self.maxsize)

    def __len__(self):
        # XXX just do unfinished_tasks property
        return self.task_queue.unfinished_tasks

    def _get_size(self):
        return self._size

    def _set_size(self, size):
        if size < 0:
            raise ValueError('Size of the pool cannot be negative: %r' % (size, ))
        if size > self._maxsize:
            raise ValueError('Size of the pool cannot be bigger than maxsize: %r > %r' % (size, self._maxsize))
        if self.manager:
            self.manager.kill()
        while self._size < size:
            self._add_thread()
        delay = 0.0001
        while self._size > size:
            while self._size - size > self.task_queue.unfinished_tasks:
                self.task_queue.put(None)
            if getcurrent() is self.hub:
                break
            sleep(delay)
            delay = min(delay * 2, .05)
        if self._size:
            self.fork_watcher.start(self._on_fork)
        else:
            self.fork_watcher.stop()

    size = property(_get_size, _set_size)

    def _init(self, maxsize):
        self._size = 0
        self._semaphore = Semaphore(1)
        self._lock = Lock()
        self.task_queue = Queue()
        self._set_maxsize(maxsize)

    def _on_fork(self):
        # fork() only leaves one thread; also screws up locks;
        # let's re-create locks and threads.
        # NOTE: See comment in gevent.hub.reinit.
        pid = os.getpid()
        if pid != self.pid:
            self.pid = pid
            # Do not mix fork() and threads; since fork() only copies one thread
            # all objects referenced by other threads has refcount that will never
            # go down to 0.
            self._init(self._maxsize)

    def join(self):
        delay = 0.0005
        while self.task_queue.unfinished_tasks > 0:
            sleep(delay)
            delay = min(delay * 2, .05)

    def kill(self):
        self.size = 0

    def _adjust_step(self):
        # if there is a possibility & necessity for adding a thread, do it
        while self._size < self._maxsize and self.task_queue.unfinished_tasks > self._size:
            self._add_thread()
        # while the number of threads is more than maxsize, kill one
        # we do not check what's already in task_queue - it could be all Nones
        while self._size - self._maxsize > self.task_queue.unfinished_tasks:
            self.task_queue.put(None)
        if self._size:
            self.fork_watcher.start(self._on_fork)
        else:
            self.fork_watcher.stop()

    def _adjust_wait(self):
        delay = 0.0001
        while True:
            self._adjust_step()
            if self._size <= self._maxsize:
                return
            sleep(delay)
            delay = min(delay * 2, .05)

    def adjust(self):
        self._adjust_step()
        if not self.manager and self._size > self._maxsize:
            # might need to feed more Nones into the pool
            self.manager = Greenlet.spawn(self._adjust_wait)

    def _add_thread(self):
        with self._lock:
            self._size += 1
        try:
            start_new_thread(self._worker, ())
        except:
            with self._lock:
                self._size -= 1
            raise

    def spawn(self, func, *args, **kwargs):
        while True:
            semaphore = self._semaphore
            semaphore.acquire()
            if semaphore is self._semaphore:
                break
        try:
            task_queue = self.task_queue
            result = AsyncResult()
            thread_result = ThreadResult(result, hub=self.hub)
            task_queue.put((func, args, kwargs, thread_result))
            self.adjust()
            # rawlink() must be the last call
            result.rawlink(lambda *args: self._semaphore.release())
            # XXX this _semaphore.release() is competing for order with get()
            # XXX this is not good, just make ThreadResult release the semaphore before doing anything else
        except:
            semaphore.release()
            raise
        return result

    def _decrease_size(self):
        if sys is None:
            return
        _lock = getattr(self, '_lock', None)
        if _lock is not None:
            with _lock:
                self._size -= 1

    def _worker(self):
        need_decrease = True
        try:
            while True:
                task_queue = self.task_queue
                task = task_queue.get()
                try:
                    if task is None:
                        need_decrease = False
                        self._decrease_size()
                        # we want first to decrease size, then decrease unfinished_tasks
                        # otherwise, _adjust might think there's one more idle thread that
                        # needs to be killed
                        return
                    func, args, kwargs, thread_result = task
                    try:
                        value = func(*args, **kwargs)
                    except:
                        exc_info = getattr(sys, 'exc_info', None)
                        if exc_info is None:
                            return
                        thread_result.handle_error((self, func), exc_info())
                    else:
                        if sys is None:
                            return
                        thread_result.set(value)
                        del value
                    finally:
                        del func, args, kwargs, thread_result, task
                finally:
                    if sys is None:
                        return
                    task_queue.task_done()
        finally:
            if need_decrease:
                self._decrease_size()

    def apply_e(self, expected_errors, function, args=None, kwargs=None):
        # Deprecated but never documented. In the past, before
        # self.apply() allowed all errors to be raised to the caller,
        # expected_errors allowed a caller to specify a set of errors
        # they wanted to be raised, through the wrap_errors function.
        # In practice, it always took the value Exception or
        # BaseException.
        return self.apply(function, args, kwargs)

    def _apply_immediately(self):
        # we always pass apply() off to the threadpool
        return False

    def _apply_async_cb_spawn(self, callback, result):
        callback(result)

    def _apply_async_use_greenlet(self):
        # Always go to Greenlet because our self.spawn uses threads
        return True


class ThreadResult(object):

    exc_info = ()

    def __init__(self, receiver, hub=None):
        if hub is None:
            hub = get_hub()
        self.receiver = receiver
        self.hub = hub
        self.value = None
        self.context = None
        self.async = hub.loop.async()
        self.async.start(self._on_async)

    @property
    def exception(self):
        return self.exc_info[1] if self.exc_info else None

    def _on_async(self):
        self.async.stop()
        try:
            if self.exc_info:
                self.hub.handle_error(self.context, *self.exc_info)
            self.context = None
            self.async = None
            self.hub = None
            if self.receiver is not None:
                self.receiver(self)
        finally:
            self.receiver = None
            self.value = None
            if self.exc_info:
                self.exc_info = (self.exc_info[0], self.exc_info[1], None)

    def set(self, value):
        self.value = value
        self.async.send()

    def handle_error(self, context, exc_info):
        self.context = context
        self.exc_info = exc_info
        self.async.send()

    # link protocol:
    def successful(self):
        return self.exception is None


def wrap_errors(errors, function, args, kwargs):
    # Deprecated but never documented.
    try:
        return True, function(*args, **kwargs)
    except errors as ex:
        return False, ex
