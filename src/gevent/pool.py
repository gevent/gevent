# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
"""
Managing greenlets in a group.

The :class:`Group` class in this module abstracts a group of running
greenlets. When a greenlet dies, it's automatically removed from the
group. All running greenlets in a group can be waited on with
:meth:`Group.join`, or all running greenlets can be killed with
:meth:`Group.kill`.

The :class:`Pool` class, which is a subclass of :class:`Group`,
provides a way to limit concurrency: its :meth:`spawn <Pool.spawn>`
method blocks if the number of greenlets in the pool has already
reached the limit, until there is a free slot.
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
    """
    At iterator of map results.
    """

    _zipped = False

    def __init__(self, func, iterable, spawn=None, maxsize=None, _zipped=False):
        """
        An iterator that.

        :keyword int maxsize: If given and not-None, specifies the maximum number of
            finished results that will be allowed to accumulated awaiting the reader;
            more than that number of results will cause map function greenlets to begin
            to block. This is most useful is there is a great disparity in the speed of
            the mapping code and the consumer and the results consume a great deal of resources.
            Using a bound is more computationally expensive than not using a bound.

        .. versionchanged:: 1.1b3
            Added the *maxsize* parameter.
        """
        from gevent.queue import Queue
        Greenlet.__init__(self)
        if spawn is not None:
            self.spawn = spawn
        if _zipped:
            self._zipped = _zipped
        self.func = func
        self.iterable = iterable
        self.queue = Queue()
        if maxsize:
            # Bounding the queue is not enough if we want to keep from
            # accumulating objects; the result value will be around as
            # the greenlet's result, blocked on self.queue.put(), and
            # we'll go on to spawn another greenlet, which in turn can
            # create the result. So we need a semaphore to prevent a
            # greenlet from exiting while the queue is full so that we
            # don't spawn the next greenlet (assuming that self.spawn
            # is of course bounded). (Alternatively we could have the
            # greenlet itself do the insert into the pool, but that
            # takes some rework).
            #
            # Given the use of a semaphore at this level, sizing the queue becomes
            # redundant, and that lets us avoid having to use self.link() instead
            # of self.rawlink() to avoid having blocking methods called in the
            # hub greenlet.
            factory = Semaphore
        else:
            factory = DummySemaphore
        self._result_semaphore = factory(maxsize)

        self.count = 0
        self.finished = False
        # If the queue size is unbounded, then we want to call all
        # the links (_on_finish and _on_result) directly in the hub greenlet
        # for efficiency. However, if the queue is bounded, we can't do that if
        # the queue might block (because if there's no waiter the hub can switch to,
        # the queue simply raises Full). Therefore, in that case, we use
        # the safer, somewhat-slower (because it spawns a greenlet) link() methods.
        # This means that _on_finish and _on_result can be called and interleaved in any order
        # if the call to self.queue.put() blocks..
        # Note that right now we're not bounding the queue, instead using a semaphore.
        self.rawlink(self._on_finish)

    def __iter__(self):
        return self

    def next(self):
        self._result_semaphore.release()
        value = self._inext()
        if isinstance(value, Failure):
            raise value.exc
        return value
    __next__ = next

    def _inext(self):
        return self.queue.get()

    def _ispawn(self, func, item):
        self._result_semaphore.acquire()
        self.count += 1
        g = self.spawn(func, item) if not self._zipped else self.spawn(func, *item)
        g.rawlink(self._on_result)
        return g

    def _run(self): # pylint:disable=method-hidden
        try:
            func = self.func
            for item in self.iterable:
                self._ispawn(func, item)
        finally:
            self.__dict__.pop('spawn', None)
            self.__dict__.pop('func', None)
            self.__dict__.pop('iterable', None)

    def _on_result(self, greenlet):
        # This method can either be called in the hub greenlet (if the
        # queue is unbounded) or its own greenlet. If it's called in
        # its own greenlet, the calls to put() may block and switch
        # greenlets, which in turn could mutate our state. So any
        # state on this object that we need to look at, notably
        # self.count, we need to capture or mutate *before* we put.
        # (Note that right now we're not bounding the queue, but we may
        # choose to do so in the future so this implementation will be left in case.)
        self.count -= 1
        count = self.count
        finished = self.finished
        ready = self.ready()
        put_finished = False

        if ready and count <= 0 and not finished:
            finished = self.finished = True
            put_finished = True

        if greenlet.successful():
            self.queue.put(self._iqueue_value_for_success(greenlet))
        else:
            self.queue.put(self._iqueue_value_for_failure(greenlet))

        if put_finished:
            self.queue.put(self._iqueue_value_for_finished())

    def _on_finish(self, _self):
        if self.finished:
            return

        if not self.successful():
            self.finished = True
            self.queue.put(self._iqueue_value_for_self_failure())
            return

        if self.count <= 0:
            self.finished = True
            self.queue.put(self._iqueue_value_for_finished())

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

    def __init__(self, *args, **kwargs):
        self.waiting = []  # QQQ maybe deque will work faster there?
        self.index = 0
        self.maxindex = -1
        IMapUnordered.__init__(self, *args, **kwargs)

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
    # blocks until the results of func are available, and a `link` method.

    # - self._apply_immediately(): should the function passed to apply be called immediately,
    # synchronously?

    # - self._apply_async_use_greenlet(): Should apply_async directly call
    # Greenlet.spawn(), bypassing self.spawn? Return true when self.spawn would block

    # - self._apply_async_cb_spawn(callback, result): Run the given callback function, possiblly
    # asynchronously, possibly synchronously.

    def apply_cb(self, func, args=None, kwds=None, callback=None):
        """
        :meth:`apply` the given *func(\\*args, \\*\\*kwds)*, and, if a *callback* is given, run it with the
        results of *func* (unless an exception was raised.)

        The *callback* may be called synchronously or asynchronously. If called
        asynchronously, it will not be tracked by this group. (:class:`Group` and :class:`Pool`
        call it asynchronously in a new greenlet; :class:`~gevent.threadpool.ThreadPool` calls
        it synchronously in the current greenlet.)
        """
        result = self.apply(func, args, kwds)
        if callback is not None:
            self._apply_async_cb_spawn(callback, result)
        return result

    def apply_async(self, func, args=None, kwds=None, callback=None):
        """
        A variant of the :meth:`apply` method which returns a :class:`~.Greenlet` object.

        When the returned greenlet gets to run, it *will* call :meth:`apply`,
        passing in *func*, *args* and *kwds*.

        If *callback* is specified, then it should be a callable which
        accepts a single argument. When the result becomes ready
        callback is applied to it (unless the call failed).

        This method will never block, even if this group is full (that is,
        even if :meth:`spawn` would block, this method will not).

        .. caution:: The returned greenlet may or may not be tracked
           as part of this group, so :meth:`joining <join>` this group is
           not a reliable way to wait for the results to be available or
           for the returned greenlet to run; instead, join the returned
           greenlet.

        .. tip:: Because :class:`~.ThreadPool` objects do not track greenlets, the returned
           greenlet will never be a part of it. To reduce overhead and improve performance,
           :class:`Group` and :class:`Pool` may choose to track the returned
           greenlet. These are implementation details that may change.
        """
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        if self._apply_async_use_greenlet():
            # cannot call self.spawn() directly because it will block
            # XXX: This is always the case for ThreadPool, but for Group/Pool
            # of greenlets, this is only the case when they are full...hence
            # the weasely language about "may or may not be tracked". Should we make
            # Group/Pool always return true as well so it's never tracked by any
            # implementation? That would simplify that logic, but could increase
            # the total number of greenlets in the system and add a layer of
            # overhead for the simple cases when the pool isn't full.
            return Greenlet.spawn(self.apply_cb, func, args, kwds, callback)

        greenlet = self.spawn(func, *args, **kwds)
        if callback is not None:
            greenlet.link(pass_value(callback))
        return greenlet

    def apply(self, func, args=None, kwds=None):
        """
        Rough quivalent of the :func:`apply()` builtin function blocking until
        the result is ready and returning it.

        The ``func`` will *usually*, but not *always*, be run in a way
        that allows the current greenlet to switch out (for example,
        in a new greenlet or thread, depending on implementation). But
        if the current greenlet or thread is already one that was
        spawned by this pool, the pool may choose to immediately run
        the `func` synchronously.

        Any exception ``func`` raises will be propagated to the caller of ``apply`` (that is,
        this method will raise the exception that ``func`` raised).
        """
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        if self._apply_immediately():
            return func(*args, **kwds)
        return self.spawn(func, *args, **kwds).get()

    def map(self, func, iterable):
        """Return a list made by applying the *func* to each element of
        the iterable.

        .. seealso:: :meth:`imap`
        """
        return list(self.imap(func, iterable))

    def map_cb(self, func, iterable, callback=None):
        result = self.map(func, iterable)
        if callback is not None:
            callback(result)
        return result

    def map_async(self, func, iterable, callback=None):
        """
        A variant of the map() method which returns a Greenlet object that is executing
        the map function.

        If callback is specified then it should be a callable which accepts a
        single argument.
        """
        return Greenlet.spawn(self.map_cb, func, iterable, callback)

    def __imap(self, cls, func, *iterables, **kwargs):
        # Python 2 doesn't support the syntax that lets us mix varargs and
        # a named kwarg, so we have to unpack manually
        maxsize = kwargs.pop('maxsize', None)
        if kwargs:
            raise TypeError("Unsupported keyword arguments")
        return cls.spawn(func, izip(*iterables), spawn=self.spawn,
                         _zipped=True, maxsize=maxsize)

    def imap(self, func, *iterables, **kwargs):
        """
        imap(func, *iterables, maxsize=None) -> iterable

        An equivalent of :func:`itertools.imap`, operating in parallel.
        The *func* is applied to each element yielded from each
        iterable in *iterables* in turn, collecting the result.

        If this object has a bound on the number of active greenlets it can
        contain (such as :class:`Pool`), then at most that number of tasks will operate
        in parallel.

        :keyword int maxsize: If given and not-None, specifies the maximum number of
            finished results that will be allowed to accumulate awaiting the reader;
            more than that number of results will cause map function greenlets to begin
            to block. This is most useful if there is a great disparity in the speed of
            the mapping code and the consumer and the results consume a great deal of resources.

            .. note:: This is separate from any bound on the number of active parallel
               tasks, though they may have some interaction (for example, limiting the
               number of parallel tasks to the smallest bound).

            .. note:: Using a bound is slightly more computationally expensive than not using a bound.

            .. tip:: The :meth:`imap_unordered` method makes much better
                use of this parameter. Some additional, unspecified,
                number of objects may be required to be kept in memory
                to maintain order by this function.

        :return: An iterable object.

        .. versionchanged:: 1.1b3
            Added the *maxsize* keyword parameter.
        .. versionchanged:: 1.1a1
            Accept multiple *iterables* to iterate in parallel.
        """
        return self.__imap(IMap, func, *iterables, **kwargs)

    def imap_unordered(self, func, *iterables, **kwargs):
        """
        imap_unordered(func, *iterables, maxsize=None) -> iterable

        The same as :meth:`imap` except that the ordering of the results
        from the returned iterator should be considered in arbitrary
        order.

        This is lighter weight than :meth:`imap` and should be preferred if order
        doesn't matter.

        .. seealso:: :meth:`imap` for more details.
        """
        return self.__imap(IMapUnordered, func, *iterables, **kwargs)


class Group(GroupMappingMixin):
    """
    Maintain a group of greenlets that are still running, without
    limiting their number.

    Links to each item and removes it upon notification.

    Groups can be iterated to discover what greenlets they are tracking,
    they can be tested to see if they contain a greenlet, and they know the
    number (len) of greenlets they are tracking. If they are not tracking any
    greenlets, they are False in a boolean context.
    """

    #: The type of Greenlet object we will :meth:`spawn`. This can be changed
    #: on an instance or in a subclass.
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
        """
        Answer how many greenlets we are tracking. Note that if we are empty,
        we are False in a boolean context.
        """
        return len(self.greenlets)

    def __contains__(self, item):
        """
        Answer if we are tracking the given greenlet.
        """
        return item in self.greenlets

    def __iter__(self):
        """
        Iterate across all the greenlets we are tracking, in no particular order.
        """
        return iter(self.greenlets)

    def add(self, greenlet):
        """
        Begin tracking the greenlet.

        If this group is :meth:`full`, then this method may block
        until it is possible to track the greenlet.
        """
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
        """
        Stop tracking the greenlet.
        """
        self._discard(greenlet)
        try:
            unlink = greenlet.unlink
        except AttributeError:
            pass  # non-Greenlet greenlet, like MAIN
        else:
            unlink(self._discard)

    def start(self, greenlet):
        """
        Start the un-started *greenlet* and add it to the collection of greenlets
        this group is monitoring.
        """
        self.add(greenlet)
        greenlet.start()

    def spawn(self, *args, **kwargs):
        """
        Begin a new greenlet with the given arguments (which are passed
        to the greenlet constructor) and add it to the collection of greenlets
        this group is monitoring.

        :return: The newly started greenlet.
        """
        greenlet = self.greenlet_class(*args, **kwargs)
        self.start(greenlet)
        return greenlet

#     def close(self):
#         """Prevents any more tasks from being submitted to the pool"""
#         self.add = RaiseException("This %s has been closed" % self.__class__.__name__)

    def join(self, timeout=None, raise_error=False):
        """
        Wait for this group to become empty *at least once*.

        If there are no greenlets in the group, returns immediately.

        .. note:: By the time the waiting code (the caller of this
           method) regains control, a greenlet may have been added to
           this group, and so this object may no longer be empty. (That
           is, ``group.join(); assert len(group) == 0`` is not
           guaranteed to hold.) This method only guarantees that the group
           reached a ``len`` of 0 at some point.

        :keyword bool raise_error: If True (*not* the default), if any
            greenlet that finished while the join was in progress raised
            an exception, that exception will be raised to the caller of
            this method. If multiple greenlets raised exceptions, which
            one gets re-raised is not determined. Only greenlets currently
            in the group when this method is called are guaranteed to
            be checked for exceptions.

        :return bool: A value indicating whether this group became empty.
           If the timeout is specified and the group did not become empty
           during that timeout, then this will be a false value. Otherwise
           it will be a true value.

        .. versionchanged:: 1.2a1
           Add the return value.
        """
        greenlets = list(self.greenlets) if raise_error else ()
        result = self._empty_event.wait(timeout=timeout)

        for greenlet in greenlets:
            if greenlet.exception is not None:
                if hasattr(greenlet, '_raise_exception'):
                    greenlet._raise_exception()
                raise greenlet.exception

        return result

    def kill(self, exception=GreenletExit, block=True, timeout=None):
        """
        Kill all greenlets being tracked by this group.
        """
        timer = Timeout._start_new_or_dummy(timeout)
        try:
            while self.greenlets:
                for greenlet in list(self.greenlets):
                    if greenlet in self.dying:
                        continue
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
        """
        If the given *greenlet* is running and being tracked by this group,
        kill it.
        """
        if greenlet not in self.dying and greenlet in self.greenlets:
            greenlet.kill(exception, block=False)
            self.dying.add(greenlet)
            if block:
                greenlet.join(timeout)

    def full(self):
        """
        Return a value indicating whether this group can track more greenlets.

        In this implementation, because there are no limits on the number of
        tracked greenlets, this will always return a ``False`` value.
        """
        return False

    def wait_available(self, timeout=None):
        """
        Block until it is possible to :meth:`spawn` a new greenlet.

        In this implementation, because there are no limits on the number
        of tracked greenlets, this will always return immediately.
        """
        pass

    # MappingMixin methods

    def _apply_immediately(self):
        # If apply() is called from one of our own
        # worker greenlets, don't spawn a new one---if we're full, that
        # could deadlock.
        return getcurrent() in self

    def _apply_async_cb_spawn(self, callback, result):
        Greenlet.spawn(callback, result)

    def _apply_async_use_greenlet(self):
        # cannot call self.spawn() because it will block, so
        # use a fresh, untracked greenlet that when run will
        # (indirectly) call self.spawn() for us.
        return self.full()


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
        """
        Create a new pool.

        A pool is like a group, but the maximum number of members
        is governed by the *size* parameter.

        :keyword int size: If given, this non-negative integer is the
            maximum count of active greenlets that will be allowed in
            this pool. A few values have special significance:

            * ``None`` (the default) places no limit on the number of
              greenlets. This is useful when you need to track, but not limit,
              greenlets, as with :class:`gevent.pywsgi.WSGIServer`. A :class:`Group`
              may be a more efficient way to achieve the same effect.
            * ``0`` creates a pool that can never have any active greenlets. Attempting
              to spawn in this pool will block forever. This is only useful
              if an application uses :meth:`wait_available` with a timeout and checks
              :meth:`free_count` before attempting to spawn.
        """
        if size is not None and size < 0:
            raise ValueError('size must not be negative: %r' % (size, ))
        Group.__init__(self)
        self.size = size
        if greenlet_class is not None:
            self.greenlet_class = greenlet_class
        if size is None:
            factory = DummySemaphore
        else:
            factory = Semaphore
        self._semaphore = factory(size)

    def wait_available(self, timeout=None):
        """
        Wait until it's possible to spawn a greenlet in this pool.

        :param float timeout: If given, only wait the specified number
            of seconds.

        .. warning:: If the pool was initialized with a size of 0, this
           method will block forever unless a timeout is given.

        :return: A number indicating how many new greenlets can be put into
           the pool without blocking.

        .. versionchanged:: 1.1a3
            Added the ``timeout`` parameter.
        """
        return self._semaphore.wait(timeout=timeout)

    def full(self):
        """
        Return a boolean indicating whether this pool has any room for
        members. (True if it does, False if it doesn't.)
        """
        return self.free_count() <= 0

    def free_count(self):
        """
        Return a number indicating *approximately* how many more members
        can be added to this pool.
        """
        if self.size is None:
            return 1
        return max(0, self.size - len(self))

    def add(self, greenlet):
        """
        Begin tracking the given greenlet, blocking until space is available.

        .. seealso:: :meth:`Group.add`
        """
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
