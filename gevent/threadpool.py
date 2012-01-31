# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
from __future__ import with_statement
import sys
import os
from gevent.hub import get_hub, sleep
from gevent.event import AsyncResult
from gevent.greenlet import Greenlet
from gevent.pool import IMap, IMapUnordered
from gevent.coros import Semaphore
from gevent._threading import Lock, Queue, start_new_thread
from gevent.six import integer_types


__all__ = ['ThreadPool',
           'ThreadResult']


class ThreadPool(object):

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
        return self.task_queue.unfinished_tasks

    @property
    def size(self):
        return self._size

    def _init(self, maxsize):
        self._size = 0
        self._semaphore = Semaphore(1)
        self._lock = Lock()
        self.task_queue = Queue()
        self._set_maxsize(maxsize)

    def _on_fork(self):
        # fork() only leaves one thread; also screws up locks;
        # let's re-create locks and threads
        pid = os.getpid()
        if pid != self.pid:
            self.pid = pid
            if self._size > 0:
                # Do not mix fork() and threads; since fork() only copies one thread
                # all objects referenced by other threads has refcount that will never
                # go down to 0.
                sys.stderr.write("WARNING: Mixing fork() and threads detected; memory leaked.\n")
            self._init(self._maxsize)

    def join(self):
        delay = 0.0005
        while self.task_queue.unfinished_tasks > 0:
            sleep(delay)
            delay = min(delay * 2, .05)

    def kill(self):
        if self.manager:
            self.manager.kill()
        self._manage(0)

    def _adjust(self, maxsize):
        if maxsize is None:
            maxsize = self._maxsize
        while self.task_queue.unfinished_tasks > self._size and self._size < maxsize:
            self._add_thread()
        while self._size - maxsize > self.task_queue.unfinished_tasks:
            self.task_queue.put(None)
        if self._size:
            self.fork_watcher.start(self._on_fork)
        else:
            self.fork_watcher.stop()

    def _manage(self, maxsize=None):
        if maxsize is None:
            maxsize = self._maxsize
        delay = 0.0001
        while True:
            self._adjust(maxsize)
            if self._size <= maxsize:
                return
            sleep(delay)
            delay = min(delay * 2, .05)

    def adjust(self):
        if self.manager:
            return
        if self._adjust(self.maxsize):
            return
        self.manager = Greenlet.spawn(self._manage)

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
                    func, args, kwargs, result = task
                    try:
                        value = func(*args, **kwargs)
                    except:
                        exc_info = getattr(sys, 'exc_info', None)
                        if exc_info is None:
                            return
                        result.handle_error(func, exc_info())
                    else:
                        if sys is None:
                            return
                        result.set(value)
                finally:
                    if sys is None:
                        return
                    task_queue.task_done()
        finally:
            if need_decrease:
                self._decrease_size()

    def apply_e(self, expected_errors, function, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        success, result = self.spawn(wrap_errors, expected_errors, function, args, kwargs).get()
        if success:
            return result
        raise result

    def apply(self, func, args=None, kwds=None):
        """Equivalent of the apply() builtin function. It blocks till the result is ready."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        return self.spawn(func, *args, **kwds).get()

    def apply_cb(self, func, args=None, kwds=None, callback=None):
        result = self.apply(func, args, kwds)
        if callback is not None:
            callback(result)
        return result

    def apply_async(self, func, args=None, kwds=None, callback=None):
        """A variant of the apply() method which returns a Greenlet object.

        If callback is specified then it should be a callable which accepts a single argument. When the result becomes ready
        callback is applied to it (unless the call failed)."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        return Greenlet.spawn(self.apply_cb, func, args, kwds, callback)

    def map(self, func, iterable):
        return list(self.imap(func, iterable))

    def map_cb(self, func, iterable, callback=None):
        result = self.map(func, iterable)
        if callback is not None:
            callback(result)
        return result

    def map_async(self, func, iterable, callback=None):
        """
        A variant of the map() method which returns a Greenlet object.

        If callback is specified then it should be a callable which accepts a
        single argument.
        """
        return Greenlet.spawn(self.map_cb, func, iterable, callback)

    def imap(self, func, iterable):
        """An equivalent of itertools.imap()"""
        return IMap.spawn(func, iterable, spawn=self.spawn)

    def imap_unordered(self, func, iterable):
        """The same as imap() except that the ordering of the results from the
        returned iterator should be considered in arbitrary order."""
        return IMapUnordered.spawn(func, iterable, spawn=self.spawn)


class ThreadResult(object):

    def __init__(self, receiver, hub=None):
        if hub is None:
            hub = get_hub()
        self.receiver = receiver
        self.hub = hub
        self.value = None
        self.context = None
        self.exc_info = None
        self.async = hub.loop.async()
        self.async.start(self._on_async)

    def _on_async(self):
        self.async.stop()
        try:
            if self.exc_info is not None:
                try:
                    self.hub.handle_error(self.context, *self.exc_info)
                finally:
                    self.exc_info = None
            self.context = None
            self.async = None
            self.hub = None
            if self.receiver is not None:
                self.receiver(self)
        finally:
            self.receiver = None
            self.value = None

    def set(self, value):
        self.value = value
        self.async.send()

    def handle_error(self, context, exc_info):
        self.context = context
        self.exc_info = exc_info
        self.async.send()

    # link protocol:
    def successful(self):
        return True


def wrap_errors(errors, function, args, kwargs):
    try:
        return True, function(*args, **kwargs)
    except errors:
        return False, sys.exc_info()[1]
