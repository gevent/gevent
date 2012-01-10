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
        self._init(maxsize)
        self.pid = os.getpid()
        self.fork_watcher = hub.loop.fork(ref=False)
        self.fork_watcher.start(self._on_fork)

    def _set_maxsize(self, maxsize):
        if not isinstance(maxsize, integer_types):
            raise TypeError('maxsize must be integer: %r' % (maxsize, ))
        if maxsize < 0:
            raise ValueError('maxsize must not be negative: %r' % (maxsize, ))
        difference = maxsize - self._maxsize
        self._semaphore.counter += difference
        self._maxsize = maxsize
        self._remove_threads()
        self._add_threads()
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
        delay = 0.0005
        while self._size > 0:
            self._remove_threads(0)
            sleep(delay)
            delay = min(delay * 2, .05)

    def _add_threads(self):
        while self.task_queue.unfinished_tasks > self._size:
            if self._size >= self.maxsize:
                break
            self._add_thread()

    def _remove_threads(self, maxsize=None):
        if maxsize is None:
            maxsize = self._maxsize
        excess = self._size - maxsize
        if excess > 0:
            while excess > self.task_queue.qsize():
                self.task_queue.put(None)

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
            tr = ThreadResult(result, hub=self.hub)
            self._remove_threads()
            task_queue.put((func, args, kwargs, tr))
            self._add_threads()
            result.rawlink(lambda *args: self._semaphore.release())
        except:
            semaphore.release()
            raise
        return result

    def _worker(self):
        try:
            while True:
                task_queue = self.task_queue
                task = task_queue.get()
                try:
                    if task is None:
                        return
                    func, args, kwargs, result = task
                    try:
                        value = func(*args, **kwargs)
                    except:
                        exc_info = getattr(sys, 'exc_info', None)
                        if exc_info is None:
                            return
                        result.set_exception(exc_info()[1])
                    else:
                        if sys is None:
                            return
                        result.set(value)
                finally:
                    if sys is None:
                        return
                    task_queue.task_done()
        finally:
            if sys is None:
                return
            _lock = getattr(self, '_lock', None)
            if _lock is not None:
                with _lock:
                    self._size -= 1

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
        self.value = None
        self.exception = None
        self.receiver = receiver
        self.async = hub.loop.async()
        self.async.start(self._on_async)

    def _on_async(self):
        self.async.stop()
        if self.receiver is not None:
            self.receiver(self)
            self.receiver = None

    def successful(self):
        return self.exception is None

    def set(self, value):
        self.value = value
        self.async.send()

    def set_exception(self, value):
        self.exception = value
        self.async.send()
