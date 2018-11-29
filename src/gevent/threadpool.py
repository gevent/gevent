# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
from __future__ import absolute_import
import sys
import os

from weakref import ref as wref

from greenlet import greenlet as RawGreenlet

from gevent._compat import integer_types
from gevent.hub import _get_hub_noargs as get_hub
from gevent.hub import getcurrent
from gevent.hub import sleep
from gevent.hub import _get_hub
from gevent.event import AsyncResult
from gevent.greenlet import Greenlet
from gevent.pool import GroupMappingMixin
from gevent.lock import Semaphore

from gevent._threading import Lock
from gevent._threading import Queue
from gevent._threading import start_new_thread
from gevent._threading import get_thread_ident


__all__ = [
    'ThreadPool',
    'ThreadResult',
]


class _WorkerGreenlet(RawGreenlet):
    # Exists to produce a more useful repr for worker pool
    # threads/greenlets.

    def __init__(self, threadpool):
        RawGreenlet.__init__(self, threadpool._worker)
        self.thread_ident = get_thread_ident()
        self._threadpool_wref = wref(threadpool)

        # Inform the gevent.util.GreenletTree that this should be
        # considered the root (for printing purposes) and to
        # ignore the parent attribute. (We can't set parent to None.)
        self.greenlet_tree_is_root = True
        self.parent.greenlet_tree_is_ignored = True

    def __repr__(self):
        return "<ThreadPoolWorker at 0x%x thread_ident=0x%x %s>" % (
            id(self),
            self.thread_ident,
            self._threadpool_wref())

class ThreadPool(GroupMappingMixin):
    """
    .. note:: The method :meth:`apply_async` will always return a new
       greenlet, bypassing the threadpool entirely.
    .. caution:: Instances of this class are only true if they have
       unfinished tasks.
    """

    def __init__(self, maxsize, hub=None):
        if hub is None:
            hub = get_hub()
        self.hub = hub
        self._maxsize = 0
        self.manager = None
        self.pid = os.getpid()
        self.fork_watcher = hub.loop.fork(ref=False)
        try:
            self._init(maxsize)
        except:
            self.fork_watcher.close()
            raise

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
        return '<%s at 0x%x %s/%s/%s hub=<%s at 0x%x thread_ident=0x%s>>' % (
            self.__class__.__name__,
            id(self),
            len(self), self.size, self.maxsize,
            self.hub.__class__.__name__, id(self.hub), self.hub.thread_ident)

    def __len__(self):
        # XXX just do unfinished_tasks property
        # Note that this becomes the boolean value of this class,
        # that's probably not what we want!
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
        delay = self.hub.loop.approx_timer_resolution
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
        """Waits until all outstanding tasks have been completed."""
        delay = max(0.0005, self.hub.loop.approx_timer_resolution)
        while self.task_queue.unfinished_tasks > 0:
            sleep(delay)
            delay = min(delay * 2, .05)

    def kill(self):
        self.size = 0
        self.fork_watcher.close()

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
            start_new_thread(self.__trampoline, ())
        except:
            with self._lock:
                self._size -= 1
            raise

    def spawn(self, func, *args, **kwargs):
        """
        Add a new task to the threadpool that will run ``func(*args, **kwargs)``.

        Waits until a slot is available. Creates a new thread if necessary.

        :return: A :class:`gevent.event.AsyncResult`.
        """
        while 1:
            semaphore = self._semaphore
            semaphore.acquire()
            if semaphore is self._semaphore:
                break

        thread_result = None
        try:
            task_queue = self.task_queue
            result = AsyncResult()
            # XXX We're calling the semaphore release function in the hub, otherwise
            # we get LoopExit (why?). Previously it was done with a rawlink on the
            # AsyncResult and the comment that it is "competing for order with get(); this is not
            # good, just make ThreadResult release the semaphore before doing anything else"
            thread_result = ThreadResult(result, self.hub, semaphore.release)
            task_queue.put((func, args, kwargs, thread_result))
            self.adjust()
        except:
            if thread_result is not None:
                thread_result.destroy()
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

    # XXX: This used to be false by default. It really seems like
    # it should be true to avoid leaking resources.
    _destroy_worker_hub = True


    def __ignore_current_greenlet_blocking(self, hub):
        if hub is not None and hub.periodic_monitoring_thread is not None:
            hub.periodic_monitoring_thread.ignore_current_greenlet_blocking()

    def __trampoline(self):
        # The target that we create new threads with. It exists
        # solely to create the _WorkerGreenlet and switch to it.
        # (the __class__ of a raw greenlet cannot be changed.)
        g = _WorkerGreenlet(self)
        g.switch()

    def _worker(self):
        # pylint:disable=too-many-branches
        need_decrease = True
        try:
            while 1: # tiny bit faster than True on Py2
                h = _get_hub()
                if h is not None:
                    h.name = 'ThreadPool Worker Hub'
                task_queue = self.task_queue
                # While we block, don't let the monitoring thread, if any,
                # report us as blocked. Indeed, so long as we never
                # try to switch greenlets, don't report us as blocked---
                # the threadpool is *meant* to run blocking tasks
                self.__ignore_current_greenlet_blocking(h)
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
                    except: # pylint:disable=bare-except
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
                        return # pylint:disable=lost-exception
                    task_queue.task_done()
        finally:
            if need_decrease:
                self._decrease_size()
            if sys is not None and self._destroy_worker_hub:
                hub = _get_hub()
                if hub is not None:
                    hub.destroy(True)
                del hub

    def apply_e(self, expected_errors, function, args=None, kwargs=None):
        """
        .. deprecated:: 1.1a2
           Identical to :meth:`apply`; the ``expected_errors`` argument is ignored.
        """
        # pylint:disable=unused-argument
        # Deprecated but never documented. In the past, before
        # self.apply() allowed all errors to be raised to the caller,
        # expected_errors allowed a caller to specify a set of errors
        # they wanted to be raised, through the wrap_errors function.
        # In practice, it always took the value Exception or
        # BaseException.
        return self.apply(function, args, kwargs)

    def _apply_immediately(self):
        # If we're being called from a different thread than the one that
        # created us, e.g., because a worker task is trying to use apply()
        # recursively, we have no choice but to run the task immediately;
        # if we try to AsyncResult.get() in the worker thread, it's likely to have
        # nothing to switch to and lead to a LoopExit.
        return get_hub() is not self.hub

    def _apply_async_cb_spawn(self, callback, result):
        callback(result)

    def _apply_async_use_greenlet(self):
        # Always go to Greenlet because our self.spawn uses threads
        return True

class _FakeAsync(object):

    def send(self):
        pass
    close = stop = send

    def __call_(self, result):
        "fake out for 'receiver'"

    def __bool__(self):
        return False

    __nonzero__ = __bool__

_FakeAsync = _FakeAsync()

class ThreadResult(object):

    # Using slots here helps to debug reference cycles/leaks
    __slots__ = ('exc_info', 'async_watcher', '_call_when_ready', 'value',
                 'context', 'hub', 'receiver')

    def __init__(self, receiver, hub, call_when_ready):
        self.receiver = receiver
        self.hub = hub
        self.context = None
        self.value = None
        self.exc_info = ()
        self.async_watcher = hub.loop.async_()
        self._call_when_ready = call_when_ready
        self.async_watcher.start(self._on_async)

    @property
    def exception(self):
        return self.exc_info[1] if self.exc_info else None

    def _on_async(self):
        self.async_watcher.stop()
        self.async_watcher.close()

        # Typically this is pool.semaphore.release and we have to
        # call this in the Hub; if we don't we get the dreaded
        # LoopExit (XXX: Why?)
        self._call_when_ready()

        try:
            if self.exc_info:
                self.hub.handle_error(self.context, *self.exc_info)
            self.context = None
            self.async_watcher = _FakeAsync
            self.hub = None
            self._call_when_ready = _FakeAsync

            self.receiver(self)
        finally:
            self.receiver = _FakeAsync
            self.value = None
            if self.exc_info:
                self.exc_info = (self.exc_info[0], self.exc_info[1], None)

    def destroy(self):
        self.async_watcher.stop()
        self.async_watcher.close()
        self.async_watcher = _FakeAsync

        self.context = None
        self.hub = None
        self._call_when_ready = _FakeAsync
        self.receiver = _FakeAsync

    def set(self, value):
        self.value = value
        self.async_watcher.send()

    def handle_error(self, context, exc_info):
        self.context = context
        self.exc_info = exc_info
        self.async_watcher.send()

    # link protocol:
    def successful(self):
        return self.exception is None


def wrap_errors(errors, function, args, kwargs):
    """
    .. deprecated:: 1.1a2
       Previously used by ThreadPool.apply_e.
    """
    try:
        return True, function(*args, **kwargs)
    except errors as ex:
        return False, ex

try:
    import concurrent.futures
except ImportError:
    pass
else:
    __all__.append("ThreadPoolExecutor")

    from gevent.timeout import Timeout as GTimeout
    from gevent._util import Lazy
    from concurrent.futures import _base as cfb

    def _wrap_error(future, fn):
        def cbwrap(_):
            del _
            # we're called with the async result, but
            # be sure to pass in ourself. Also automatically
            # unlink ourself so that we don't get called multiple
            # times.
            try:
                fn(future)
            except Exception: # pylint: disable=broad-except
                future.hub.print_exception((fn, future), *sys.exc_info())
        cbwrap.auto_unlink = True
        return cbwrap

    def _wrap(future, fn):
        def f(_):
            fn(future)
        f.auto_unlink = True
        return f

    class _FutureProxy(object):
        def __init__(self, asyncresult):
            self.asyncresult = asyncresult

        # Internal implementation details of a c.f.Future

        @Lazy
        def _condition(self):
            from gevent import monkey
            if monkey.is_module_patched('threading') or self.done():
                import threading
                return threading.Condition()
            # We can only properly work with conditions
            # when we've been monkey-patched. This is necessary
            # for the wait/as_completed module functions.
            raise AttributeError("_condition")

        @Lazy
        def _waiters(self):
            self.asyncresult.rawlink(self.__when_done)
            return []

        def __when_done(self, _):
            # We should only be called when _waiters has
            # already been accessed.
            waiters = getattr(self, '_waiters')
            for w in waiters: # pylint:disable=not-an-iterable
                if self.successful():
                    w.add_result(self)
                else:
                    w.add_exception(self)

        __when_done.auto_unlink = True

        @property
        def _state(self):
            if self.done():
                return cfb.FINISHED
            return cfb.RUNNING

        def set_running_or_notify_cancel(self):
            # Does nothing, not even any consistency checks. It's
            # meant to be internal to the executor and we don't use it.
            return

        def result(self, timeout=None):
            try:
                return self.asyncresult.result(timeout=timeout)
            except GTimeout:
                # XXX: Theoretically this could be a completely
                # unrelated timeout instance. Do we care about that?
                raise concurrent.futures.TimeoutError()

        def exception(self, timeout=None):
            try:
                self.asyncresult.get(timeout=timeout)
                return self.asyncresult.exception
            except GTimeout:
                raise concurrent.futures.TimeoutError()

        def add_done_callback(self, fn):
            if self.done():
                fn(self)
            else:
                self.asyncresult.rawlink(_wrap_error(self, fn))

        def rawlink(self, fn):
            self.asyncresult.rawlink(_wrap(self, fn))

        def __str__(self):
            return str(self.asyncresult)

        def __getattr__(self, name):
            return getattr(self.asyncresult, name)

    class ThreadPoolExecutor(concurrent.futures.ThreadPoolExecutor):
        """
        A version of :class:`concurrent.futures.ThreadPoolExecutor` that
        always uses native threads, even when threading is monkey-patched.

        The ``Future`` objects returned from this object can be used
        with gevent waiting primitives like :func:`gevent.wait`.

        .. caution:: If threading is *not* monkey-patched, then the ``Future``
           objects returned by this object are not guaranteed to work with
           :func:`~concurrent.futures.as_completed` and :func:`~concurrent.futures.wait`.
           The individual blocking methods like :meth:`~concurrent.futures.Future.result`
           and :meth:`~concurrent.futures.Future.exception` will always work.

        .. versionadded:: 1.2a1
           This is a provisional API.
        """

        def __init__(self, max_workers):
            super(ThreadPoolExecutor, self).__init__(max_workers)
            self._threadpool = ThreadPool(max_workers)
            self._threadpool._destroy_worker_hub = True

        def submit(self, fn, *args, **kwargs):
            with self._shutdown_lock: # pylint:disable=not-context-manager
                if self._shutdown:
                    raise RuntimeError('cannot schedule new futures after shutdown')

                future = self._threadpool.spawn(fn, *args, **kwargs)
                return _FutureProxy(future)

        def shutdown(self, wait=True):
            super(ThreadPoolExecutor, self).shutdown(wait)
            # XXX: We don't implement wait properly
            kill = getattr(self._threadpool, 'kill', None)
            if kill: # pylint:disable=using-constant-test
                self._threadpool.kill()
            self._threadpool = None

        kill = shutdown # greentest compat

        def _adjust_thread_count(self):
            # Does nothing. We don't want to spawn any "threads",
            # let the threadpool handle that.
            pass
