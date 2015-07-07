# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
"""Managing greenlets in a group.

The :class:`Group` class in this module abstracts a group of running greenlets.
When a greenlet dies, it's automatically removed from the group.

The :class:`Pool` which a subclass of :class:`Group` provides a way to limit
concurrency: its :meth:`spawn <Pool.spawn>` method blocks if the number of
greenlets in the pool has already reached the limit, until there is a free slot.
"""

from bisect import insort_right
try:
    from itertools import izip
except ImportError:
    # Python 3
    izip = zip

from gevent.hub import GreenletExit, getcurrent, kill as _kill
from gevent.greenlet import joinall, Greenlet
from gevent.timeout import Timeout
from gevent.event import Event
from gevent.lock import Semaphore, DummySemaphore

__all__ = ['Group', 'Pool']


class IMapUnordered(Greenlet):

    _zipped = False

    def __init__(self, func, iterable, spawn=None, _zipped=False):
        from gevent.queue import Queue
        Greenlet.__init__(self)
        if spawn is not None:
            self.spawn = spawn
        if _zipped:
            self._zipped = _zipped
        self.func = func
        self.iterable = iterable
        self.queue = Queue()
        self.count = 0
        self.finished = False
        self.rawlink(self._on_finish)

    def __iter__(self):
        return self

    def next(self):
        value = self._inext()
        if isinstance(value, Failure):
            raise value.exc
        return value
    __next__ = next

    def _inext(self):
        return self.queue.get()

    def _ispawn(self, func, item):
        self.count += 1
        g = self.spawn(func, item) if not self._zipped else self.spawn(func, *item)
        g.rawlink(self._on_result)
        return g

    def _run(self):
        try:
            func = self.func
            for item in self.iterable:
                self._ispawn(func, item)
        finally:
            self.__dict__.pop('spawn', None)
            self.__dict__.pop('func', None)
            self.__dict__.pop('iterable', None)

    def _on_result(self, greenlet):
        self.count -= 1
        if greenlet.successful():
            self.queue.put(self._iqueue_value_for_success(greenlet))
        else:
            self.queue.put(self._iqueue_value_for_failure(greenlet))

        if self.ready() and self.count <= 0 and not self.finished:
            self.queue.put(self._iqueue_value_for_finished())
            self.finished = True

    def _on_finish(self, _self):
        if self.finished:
            return

        if not self.successful():
            self.queue.put(self._iqueue_value_for_self_failure())
            self.finished = True
            return

        if self.count <= 0:
            self.queue.put(self._iqueue_value_for_finished())
            self.finished = True

    def _iqueue_value_for_success(self, greenlet):
        return greenlet.value

    def _iqueue_value_for_failure(self, greenlet):
        return Failure(greenlet.exception, getattr(greenlet, '_raise_exception'))

    def _iqueue_value_for_finished(self):
        return Failure(StopIteration)

    def _iqueue_value_for_self_failure(self):
        return Failure(self.exception, self._raise_exception)


class IMap(IMapUnordered):
    # A specialization of IMapUnordered that returns items
    # in the order in which they were generated, not
    # the order in which they finish.
    # We do this by storing tuples (order, value) in the queue
    # not just value.

    def __init__(self, func, iterable, spawn=None, _zipped=False):
        self.waiting = []  # QQQ maybe deque will work faster there?
        self.index = 0
        self.maxindex = -1
        IMapUnordered.__init__(self, func, iterable, spawn, _zipped)

    def _inext(self):
        while True:
            if self.waiting and self.waiting[0][0] <= self.index:
                _, value = self.waiting.pop(0)
            else:
                index, value = self.queue.get()
                if index > self.index:
                    insort_right(self.waiting, (index, value))
                    continue
            self.index += 1
            return value

    def _ispawn(self, func, item):
        g = IMapUnordered._ispawn(self, func, item)
        self.maxindex += 1
        g.index = self.maxindex
        return g

    def _iqueue_value_for_success(self, greenlet):
        return (greenlet.index, IMapUnordered._iqueue_value_for_success(self, greenlet))

    def _iqueue_value_for_failure(self, greenlet):
        return (greenlet.index, IMapUnordered._iqueue_value_for_failure(self, greenlet))

    def _iqueue_value_for_finished(self):
        self.maxindex += 1
        return (self.maxindex, IMapUnordered._iqueue_value_for_finished(self))

    def _iqueue_value_for_self_failure(self):
        self.maxindex += 1
        return (self.maxindex, IMapUnordered._iqueue_value_for_self_failure(self))


class GroupMappingMixin(object):
    # Internal, non-public API class.
    # Provides mixin methods for implementing mapping pools. Subclasses must define:

    # - self.spawn(func, *args, **kwargs): a function that runs `func` with `args`
    # and `awargs`, potentially asynchronously. Return a value with a `get` method that
    # blocks until the results of func are available

    # - self._apply_immediately(): should the function passed to apply be called immediately,
    # synchronously?

    # - self._apply_async_use_greenlet(): Should apply_async directly call
    # Greenlet.spawn(), bypassing self.spawn? Return true when self.spawn would block

    # - self._apply_async_cb_spawn(callback, result): Run the given callback function, possiblly
    # asynchronously, possibly synchronously.

    def apply_cb(self, func, args=None, kwds=None, callback=None):
        result = self.apply(func, args, kwds)
        if callback is not None:
            self._apply_async_cb_spawn(callback, result)
        return result

    def apply_async(self, func, args=None, kwds=None, callback=None):
        """A variant of the apply() method which returns a Greenlet object.

        If callback is specified then it should be a callable which accepts a single argument. When the result becomes ready
        callback is applied to it (unless the call failed)."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        if self._apply_async_use_greenlet():
            # cannot call spawn() directly because it will block
            return Greenlet.spawn(self.apply_cb, func, args, kwds, callback)

        greenlet = self.spawn(func, *args, **kwds)
        if callback is not None:
            greenlet.link(pass_value(callback))
        return greenlet

    def apply(self, func, args=None, kwds=None):
        """Equivalent of the apply() builtin function. It blocks till the result is ready."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        if self._apply_immediately():
            return func(*args, **kwds)
        else:
            return self.spawn(func, *args, **kwds).get()

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

    def imap(self, func, *iterables):
        """An equivalent of itertools.imap()"""
        return IMap.spawn(func, izip(*iterables), spawn=self.spawn,
                          _zipped=True)

    def imap_unordered(self, func, *iterables):
        """The same as imap() except that the ordering of the results from the
        returned iterator should be considered in arbitrary order."""
        return IMapUnordered.spawn(func, izip(*iterables), spawn=self.spawn,
                                   _zipped=True)


class Group(GroupMappingMixin):
    """Maintain a group of greenlets that are still running.

    Links to each item and removes it upon notification.
    """
    greenlet_class = Greenlet

    def __init__(self, *args):
        assert len(args) <= 1, args
        self.greenlets = set(*args)
        if args:
            for greenlet in args[0]:
                greenlet.rawlink(self._discard)
        # each item we kill we place in dying, to avoid killing the same greenlet twice
        self.dying = set()
        self._empty_event = Event()
        self._empty_event.set()

    def __repr__(self):
        return '<%s at 0x%x %s>' % (self.__class__.__name__, id(self), self.greenlets)

    def __len__(self):
        return len(self.greenlets)

    def __contains__(self, item):
        return item in self.greenlets

    def __iter__(self):
        return iter(self.greenlets)

    def add(self, greenlet):
        try:
            rawlink = greenlet.rawlink
        except AttributeError:
            pass  # non-Greenlet greenlet, like MAIN
        else:
            rawlink(self._discard)
        self.greenlets.add(greenlet)
        self._empty_event.clear()

    def _discard(self, greenlet):
        self.greenlets.discard(greenlet)
        self.dying.discard(greenlet)
        if not self.greenlets:
            self._empty_event.set()

    def discard(self, greenlet):
        self._discard(greenlet)
        try:
            unlink = greenlet.unlink
        except AttributeError:
            pass  # non-Greenlet greenlet, like MAIN
        else:
            unlink(self._discard)

    def start(self, greenlet):
        self.add(greenlet)
        greenlet.start()

    def spawn(self, *args, **kwargs):
        greenlet = self.greenlet_class(*args, **kwargs)
        self.start(greenlet)
        return greenlet

#     def close(self):
#         """Prevents any more tasks from being submitted to the pool"""
#         self.add = RaiseException("This %s has been closed" % self.__class__.__name__)

    def join(self, timeout=None, raise_error=False):
        if raise_error:
            greenlets = self.greenlets.copy()
            self._empty_event.wait(timeout=timeout)
            for greenlet in greenlets:
                if greenlet.exception is not None:
                    if hasattr(greenlet, '_raise_exception'):
                        greenlet._raise_exception()
                    raise greenlet.exception
        else:
            self._empty_event.wait(timeout=timeout)

    def kill(self, exception=GreenletExit, block=True, timeout=None):
        timer = Timeout.start_new(timeout)
        try:
            try:
                while self.greenlets:
                    for greenlet in list(self.greenlets):
                        if greenlet not in self.dying:
                            try:
                                kill = greenlet.kill
                            except AttributeError:
                                _kill(greenlet, exception)
                            else:
                                kill(exception, block=False)
                            self.dying.add(greenlet)
                    if not block:
                        break
                    joinall(self.greenlets)
            except Timeout as ex:
                if ex is not timer:
                    raise
        finally:
            timer.cancel()

    def killone(self, greenlet, exception=GreenletExit, block=True, timeout=None):
        if greenlet not in self.dying and greenlet in self.greenlets:
            greenlet.kill(exception, block=False)
            self.dying.add(greenlet)
            if block:
                greenlet.join(timeout)

    def full(self):
        return False

    def wait_available(self):
        pass

    # MappingMixin methods

    def _apply_immediately(self):
        # If apply() is called from one of our own
        # worker greenlets, don't spawn a new one
        return getcurrent() in self

    def _apply_async_cb_spawn(self, callback, result):
        Greenlet.spawn(callback, result)

    def _apply_async_use_greenlet(self):
        return self.full() # cannot call self.spawn() because it will block


class Failure(object):
    __slots__ = ['exc', '_raise_exception']

    def __init__(self, exc, raise_exception=None):
        self.exc = exc
        self._raise_exception = raise_exception

    def raise_exc(self):
        if self._raise_exception:
            self._raise_exception()
        else:
            raise self.exc


class Pool(Group):

    def __init__(self, size=None, greenlet_class=None):
        if size is not None and size < 0:
            raise ValueError('size must not be negative: %r' % (size, ))
        Group.__init__(self)
        self.size = size
        if greenlet_class is not None:
            self.greenlet_class = greenlet_class
        if size is None:
            self._semaphore = DummySemaphore()
        else:
            self._semaphore = Semaphore(size)

    def wait_available(self):
        self._semaphore.wait()

    def full(self):
        return self.free_count() <= 0

    def free_count(self):
        if self.size is None:
            return 1
        return max(0, self.size - len(self))

    def add(self, greenlet):
        self._semaphore.acquire()
        try:
            Group.add(self, greenlet)
        except:
            self._semaphore.release()
            raise

    def _discard(self, greenlet):
        Group._discard(self, greenlet)
        self._semaphore.release()


class pass_value(object):
    __slots__ = ['callback']

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, source):
        if source.successful():
            self.callback(source.value)

    def __hash__(self):
        return hash(self.callback)

    def __eq__(self, other):
        return self.callback == getattr(other, 'callback', other)

    def __str__(self):
        return str(self.callback)

    def __repr__(self):
        return repr(self.callback)

    def __getattr__(self, item):
        assert item != 'callback'
        return getattr(self.callback, item)
