# Copyright (c) 2009-2015 Denis Bilenko. See LICENSE for details.
"""
Event-loop hub.
"""
from __future__ import absolute_import
import sys
import os
import traceback

from greenlet import greenlet, getcurrent, GreenletExit


__all__ = ['getcurrent',
           'GreenletExit',
           'spawn_raw',
           'sleep',
           'kill',
           'signal',
           'reinit',
           'get_hub',
           'Hub',
           'Waiter']

# Sniff Python > 2.7.9 for new SSL interfaces
# If True, Python is greater than or equal to 2.7.9 (but not Python 3).
PYGTE279 = (
    sys.version_info[0] == 2
    and sys.version_info[1] >= 7
    and sys.version_info[2] >= 9
)

PY3 = sys.version_info[0] >= 3
PYPY = hasattr(sys, 'pypy_version_info')


if PY3:
    string_types = str,
    integer_types = int,
    text_type = str
    xrange = range

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

else:
    import __builtin__
    string_types = __builtin__.basestring,
    text_type = __builtin__.unicode
    integer_types = (int, __builtin__.long)
    xrange = __builtin__.xrange

    from gevent._util_py2 import reraise


if sys.version_info[0] <= 2:
    import thread
else:
    import _thread as thread
threadlocal = thread._local
_threadlocal = threadlocal()
_threadlocal.Hub = None
get_ident = thread.get_ident
MAIN_THREAD = get_ident()


class LoopExit(Exception):
    pass


class BlockingSwitchOutError(AssertionError):
    pass


class InvalidSwitchError(AssertionError):
    pass


class ConcurrentObjectUseError(AssertionError):
    # raised when an object is used (waited on) by two greenlets
    # independently, meaning the object was entered into a blocking
    # state by one greenlet and then another while still blocking in the
    # first one
    pass


def spawn_raw(function, *args):
    """
    Create a new :class:`greenlet.greenlet` object and schedule it to run ``function(*args, **kwargs)``.

    This returns a raw greenlet which does not have all the useful methods that
    :class:`gevent.Greenlet` has. Typically, applications should prefer :func:`gevent.spawn`,
    but this method may occasionally be useful as an optimization if there are many greenlets
    involved.

    .. versionchanged:: 1.1a3
        Verify that ``function`` is callable, raising a TypeError if not. Previously,
        the spawned greenlet would have failed the first time it was switched to.
    """
    if not callable(function):
        raise TypeError("function must be callable")
    hub = get_hub()
    g = greenlet(function, hub)
    hub.loop.run_callback(g.switch, *args)
    return g


def sleep(seconds=0, ref=True):
    """
    Put the current greenlet to sleep for at least *seconds*.

    *seconds* may be specified as an integer, or a float if fractional
    seconds are desired.

    .. tip:: In the current implementation, a value of 0 (the default)
       means to yield execution to any other runnable greenlets, but
       this greenlet may be scheduled again before the event loop
       cycles (in an extreme case, a greenlet that repeatedly sleeps
       with 0 can prevent greenlets that are ready to do I/O from
       being scheduled for some (small) period of time); a value greater than
       0, on the other hand, will delay running this greenlet until
       the next iteration of the loop.

    If *ref* is False, the greenlet running ``sleep()`` will not prevent :func:`gevent.wait`
    from exiting.

    .. seealso:: :func:`idle`
    """
    hub = get_hub()
    loop = hub.loop
    if seconds <= 0:
        waiter = Waiter()
        loop.run_callback(waiter.switch)
        waiter.get()
    else:
        hub.wait(loop.timer(seconds, ref=ref))


def idle(priority=0):
    """
    Cause the calling greenlet to wait until the event loop is idle.

    Idle is defined as having no other events of the same or higher
    *priority* pending. That is, as long as sockets, timeouts or even
    signals of the same or higher priority are being processed, the loop
    is not idle.

    .. seealso:: :func:`sleep`
    """
    hub = get_hub()
    watcher = hub.loop.idle()
    if priority:
        watcher.priority = priority
    hub.wait(watcher)


def kill(greenlet, exception=GreenletExit):
    """
    Kill greenlet asynchronously. The current greenlet is not unscheduled.

    .. note::

        The method :meth:`Greenlet.kill` method does the same and
        more (and the same caveats listed there apply here). However, the MAIN
        greenlet - the one that exists initially - does not have a
        ``kill()`` method, and neither do any created with :func:`spawn_raw`,
        so you have to use this function.

    .. versionchanged:: 1.1a2
        If the ``greenlet`` has a :meth:`kill <Greenlet.kill>` method, calls it. This prevents a
        greenlet from being switched to for the first time after it's been
        killed but not yet executed.
    """
    if not greenlet.dead:
        if hasattr(greenlet, 'kill'):
            # dealing with gevent.greenlet.Greenlet. Use it, especially
            # to avoid allowing one to be switched to for the first time
            # after it's been killed
            greenlet.kill(exception=exception, block=False)
        else:
            get_hub().loop.run_callback(greenlet.throw, exception)


class signal(object):
    """
    Call the *handler* with the *args* and *kwargs* when the process
    receives the signal *signalnum*.

    The *handler* will be run in a new greenlet when the signal is delivered.

    This returns an object with the useful method ``cancel``, which, when called,
    will prevent future deliveries of *signalnum* from calling *handler*.

    .. note::

        This may not operate correctly with SIGCHLD if libev child watchers
        are used (as they are by default with os.fork).
    """

    greenlet_class = None

    def __init__(self, signalnum, handler, *args, **kwargs):
        self.hub = get_hub()
        self.watcher = self.hub.loop.signal(signalnum, ref=False)
        self.watcher.start(self._start)
        self.handler = handler
        self.args = args
        self.kwargs = kwargs
        if self.greenlet_class is None:
            from gevent import Greenlet
            self.greenlet_class = Greenlet

    def _get_ref(self):
        return self.watcher.ref

    def _set_ref(self, value):
        self.watcher.ref = value

    ref = property(_get_ref, _set_ref)
    del _get_ref, _set_ref

    def cancel(self):
        self.watcher.stop()

    def _start(self):
        try:
            greenlet = self.greenlet_class(self.handle)
            greenlet.switch()
        except:
            self.hub.handle_error(None, *sys._exc_info())

    def handle(self):
        try:
            self.handler(*self.args, **self.kwargs)
        except:
            self.hub.handle_error(None, *sys.exc_info())


def reinit():
    """
    Prepare the gevent hub to run in a new (forked) process.

    This should be called *immediately* after :func:`os.fork` in the
    child process. This is done automatically by
    :func:`gevent.os.fork` or if the :mod:`os` module has been
    monkey-patched. If this function is not called in a forked
    process, symptoms may include hanging of functions like
    :func:`socket.getaddrinfo`, and the hub's threadpool is unlikely
    to work.

    .. note:: Registered fork watchers may or may not run before
       this function (and thus ``gevent.os.fork``) return. If they have
       not run, they will run "soon", after an iteration of the event loop.
       You can force this by inserting a few small (but non-zero) calls to :func:`sleep`
       after fork returns. (As of gevent 1.1 and before, fork watchers will
       not have run, but this may change in the future.)

    .. note:: This function may be removed in a future major release
       if the fork process can be more smoothly managed.

    .. warning:: See remarks in :func:`gevent.os.fork` about greenlets
       and libev watchers in the child process.
    """
    # The loop reinit function in turn calls libev's ev_loop_fork
    # function.
    hub = _get_hub()

    if hub is not None:
        # Note that we reinit the existing loop, not destroy it.
        # See https://github.com/gevent/gevent/issues/200.
        hub.loop.reinit()
        # libev's fork watchers are slow to fire because the only fire
        # at the beginning of a loop; due to our use of callbacks that
        # run at the end of the loop, that may be too late. The
        # threadpool and resolvers depend on the fork handlers being
        # run (specifically, the threadpool will fail in the forked
        # child if there were any threads in it, which there will be
        # if the resolver_thread was in use (the default) before the
        # fork.)
        #
        # If the forked process wants to use the threadpool or
        # resolver immediately (in a queued callback), it would hang.
        #
        # The below is a workaround. Fortunately, both of these
        # methods are idempotent and can be called multiple times
        # following a fork if the suddenly started working, or were
        # already working on some platforms. Other threadpools and fork handlers
        # will be called at an arbitrary time later ('soon')
        if hasattr(hub.threadpool, '_on_fork'):
            hub.threadpool._on_fork()
        # resolver_ares also has a fork watcher that's not firing
        if hasattr(hub.resolver, '_on_fork'):
            hub.resolver._on_fork()

        # TODO: We'd like to sleep for a non-zero amount of time to force the loop to make a
        # pass around before returning to this greenlet. That will allow any
        # user-provided fork watchers to run. (Two calls are necessary.) HOWEVER, if
        # we do this, certain tests that heavily mix threads and forking,
        # like 2.7/test_threading:test_reinit_tls_after_fork, fail. It's not immediately clear
        # why.
        #sleep(0.00001)
        #sleep(0.00001)


def get_hub_class():
    """Return the type of hub to use for the current thread.

    If there's no type of hub for the current thread yet, 'gevent.hub.Hub' is used.
    """
    global _threadlocal
    try:
        hubtype = _threadlocal.Hub
    except AttributeError:
        hubtype = None
    if hubtype is None:
        hubtype = _threadlocal.Hub = Hub
    return hubtype


def get_hub(*args, **kwargs):
    """
    Return the hub for the current thread.

    If a hub does not exist in the current thread, a new one is
    created of the type returned by :func:`get_hub_class`.
    """
    global _threadlocal
    try:
        return _threadlocal.hub
    except AttributeError:
        hubtype = get_hub_class()
        hub = _threadlocal.hub = hubtype(*args, **kwargs)
        return hub


def _get_hub():
    """Return the hub for the current thread.

    Return ``None`` if no hub has been created yet.
    """
    global _threadlocal
    try:
        return _threadlocal.hub
    except AttributeError:
        pass


def set_hub(hub):
    _threadlocal.hub = hub


def _import(path):
    if isinstance(path, list):
        if not path:
            raise ImportError('Cannot import from empty list: %r' % (path, ))
        for item in path[:-1]:
            try:
                return _import(item)
            except ImportError:
                pass
        return _import(path[-1])
    if not isinstance(path, string_types):
        return path
    if '.' not in path:
        raise ImportError("Cannot import %r (required format: [path/][package.]module.class)" % path)
    if '/' in path:
        package_path, path = path.rsplit('/', 1)
        sys.path = [package_path] + sys.path
    else:
        package_path = None
    try:
        module, item = path.rsplit('.', 1)
        x = __import__(module)
        for attr in path.split('.')[1:]:
            oldx = x
            x = getattr(x, attr, _NONE)
            if x is _NONE:
                raise ImportError('Cannot import %r from %r' % (attr, oldx))
        return x
    finally:
        try:
            sys.path.remove(package_path)
        except ValueError:
            pass


def config(default, envvar):
    result = os.environ.get(envvar) or default
    if isinstance(result, string_types):
        return result.split(',')
    return result


def resolver_config(default, envvar):
    result = config(default, envvar)
    return [_resolvers.get(x, x) for x in result]


_resolvers = {'ares': 'gevent.resolver_ares.Resolver',
              'thread': 'gevent.resolver_thread.Resolver',
              'block': 'gevent.socket.BlockingResolver'}


class Hub(greenlet):
    """A greenlet that runs the event loop.

    It is created automatically by :func:`get_hub`.

    **Switching**

    Every time this greenlet (i.e., the event loop) is switched *to*, if
    the current greenlet has a ``switch_out`` method, it will be called. This
    allows a greenlet to take some cleanup actions before yielding control. This method
    should not call any gevent blocking functions.
    """

    #: If instances of these classes are raised into the event loop,
    #: they will be propagated out to the main greenlet (where they will
    #: usually be caught by Python itself)
    SYSTEM_ERROR = (KeyboardInterrupt, SystemExit, SystemError)

    #: Instances of these classes are not considered to be errors and
    #: do not get logged/printed when raised by the event loop.
    NOT_ERROR = (GreenletExit, SystemExit)

    loop_class = config('gevent.core.loop', 'GEVENT_LOOP')
    resolver_class = ['gevent.resolver_thread.Resolver',
                      'gevent.resolver_ares.Resolver',
                      'gevent.socket.BlockingResolver']
    #: The class or callable object, or the name of a factory function or class,
    #: that will be used to create :attr:`resolver`. By default, configured according to
    #: :doc:`dns`. If a list, a list of objects in preference order.
    resolver_class = resolver_config(resolver_class, 'GEVENT_RESOLVER')
    threadpool_class = config('gevent.threadpool.ThreadPool', 'GEVENT_THREADPOOL')
    backend = config(None, 'GEVENT_BACKEND')
    format_context = 'pprint.pformat'
    threadpool_size = 10

    def __init__(self, loop=None, default=None):
        greenlet.__init__(self)
        if hasattr(loop, 'run'):
            if default is not None:
                raise TypeError("Unexpected argument: default")
            self.loop = loop
        else:
            if default is None and get_ident() != MAIN_THREAD:
                default = False
            loop_class = _import(self.loop_class)
            if loop is None:
                loop = self.backend
            self.loop = loop_class(flags=loop, default=default)
        self._resolver = None
        self._threadpool = None
        self.format_context = _import(self.format_context)

    def __repr__(self):
        if self.loop is None:
            info = 'destroyed'
        else:
            try:
                info = self.loop._format()
            except Exception as ex:
                info = str(ex) or repr(ex) or 'error'
        result = '<%s at 0x%x %s' % (self.__class__.__name__, id(self), info)
        if self._resolver is not None:
            result += ' resolver=%r' % self._resolver
        if self._threadpool is not None:
            result += ' threadpool=%r' % self._threadpool
        return result + '>'

    def handle_error(self, context, type, value, tb):
        """
        Called by the event loop when an error occurs. The arguments
        type, value, and tb are the standard tuple returned by :func:`sys.exc_info`.

        Applications can set a property on the hub with this same signature
        to override the error handling provided by this class.

        Errors that are :attr:`system errors <SYSTEM_ERROR>` are passed
        to :meth:`handle_system_error`.

        :param context: If this is ``None``, indicates a system error that
            should generally result in exiting the loop and being thrown to the
            parent greenlet.
        """
        if isinstance(value, str):
            # Cython can raise errors where the value is a plain string
            # e.g., AttributeError, "_semaphore.Semaphore has no attr", <traceback>
            value = type(value)
        if not issubclass(type, self.NOT_ERROR):
            self.print_exception(context, type, value, tb)
        if context is None or issubclass(type, self.SYSTEM_ERROR):
            self.handle_system_error(type, value)

    def handle_system_error(self, type, value):
        current = getcurrent()
        if current is self or current is self.parent or self.loop is None:
            self.parent.throw(type, value)
        else:
            # in case system error was handled and life goes on
            # switch back to this greenlet as well
            cb = None
            try:
                cb = self.loop.run_callback(current.switch)
            except:
                traceback.print_exc()
            try:
                self.parent.throw(type, value)
            finally:
                if cb is not None:
                    cb.stop()

    def print_exception(self, context, type, value, tb):
        # Python 3 does not gracefully handle None value or tb in
        # traceback.print_exception() as previous versions did.
        if value is None:
            sys.stderr.write('%s\n' % type.__name__)
        else:
            traceback.print_exception(type, value, tb)
        del tb
        if context is not None:
            if not isinstance(context, str):
                try:
                    context = self.format_context(context)
                except:
                    traceback.print_exc()
                    context = repr(context)
            sys.stderr.write('%s failed with %s\n\n' % (context, getattr(type, '__name__', 'exception'), ))

    def switch(self):
        switch_out = getattr(getcurrent(), 'switch_out', None)
        if switch_out is not None:
            switch_out()
        return greenlet.switch(self)

    def switch_out(self):
        raise BlockingSwitchOutError('Impossible to call blocking function in the event loop callback')

    def wait(self, watcher):
        """
        Wait until the *watcher* (which should not be started) is ready.

        The current greenlet will be unscheduled during this time.

        .. seealso:: :class:`gevent.core.io`, :class:`gevent.core.timer`,
            :class:`gevent.core.signal`, :class:`gevent.core.idle`, :class:`gevent.core.prepare`,
            :class:`gevent.core.check`, :class:`gevent.core.fork`, :class:`gevent.core.async`,
            :class:`gevent.core.child`, :class:`gevent.core.stat`

        """
        waiter = Waiter()
        unique = object()
        watcher.start(waiter.switch, unique)
        try:
            result = waiter.get()
            if result is not unique:
                raise InvalidSwitchError('Invalid switch into %s: %r (expected %r)' % (getcurrent(), result, unique))
        finally:
            watcher.stop()

    def cancel_wait(self, watcher, error):
        """
        Cancel an in-progress call to :meth:`wait` by throwing the given *error*
        in the waiting greenlet.
        """
        if watcher.callback is not None:
            self.loop.run_callback(self._cancel_wait, watcher, error)

    def _cancel_wait(self, watcher, error):
        if watcher.active:
            switch = watcher.callback
            if switch is not None:
                greenlet = getattr(switch, '__self__', None)
                if greenlet is not None:
                    greenlet.throw(error)

    def run(self):
        """
        Entry-point to running the loop. This method is called automatically
        when the hub greenlet is scheduled; do not call it directly.

        :raises LoopExit: If the loop finishes running. This means
           that there are no other scheduled greenlets, and no active
           watchers or servers. In some situations, this indicates a
           programming error.
        """
        assert self is getcurrent(), 'Do not call Hub.run() directly'
        while True:
            loop = self.loop
            loop.error_handler = self
            try:
                loop.run()
            finally:
                loop.error_handler = None  # break the refcount cycle
            self.parent.throw(LoopExit('This operation would block forever', self))
        # this function must never return, as it will cause switch() in the parent greenlet
        # to return an unexpected value
        # It is still possible to kill this greenlet with throw. However, in that case
        # switching to it is no longer safe, as switch will return immediatelly

    def join(self, timeout=None):
        """Wait for the event loop to finish. Exits only when there are
        no more spawned greenlets, started servers, active timeouts or watchers.

        If *timeout* is provided, wait no longer for the specified number of seconds.

        Returns True if exited because the loop finished execution.
        Returns False if exited because of timeout expired.
        """
        assert getcurrent() is self.parent, "only possible from the MAIN greenlet"
        if self.dead:
            return True

        waiter = Waiter()

        if timeout is not None:
            timeout = self.loop.timer(timeout, ref=False)
            timeout.start(waiter.switch)

        try:
            try:
                waiter.get()
            except LoopExit:
                return True
        finally:
            if timeout is not None:
                timeout.stop()
        return False

    def destroy(self, destroy_loop=None):
        global _threadlocal
        if self._resolver is not None:
            self._resolver.close()
            del self._resolver
        if self._threadpool is not None:
            self._threadpool.kill()
            del self._threadpool
        if destroy_loop is None:
            destroy_loop = not self.loop.default
        if destroy_loop:
            self.loop.destroy()
        self.loop = None
        if getattr(_threadlocal, 'hub', None) is self:
            del _threadlocal.hub

    def _get_resolver(self):
        if self._resolver is None:
            if self.resolver_class is not None:
                self.resolver_class = _import(self.resolver_class)
                self._resolver = self.resolver_class(hub=self)
        return self._resolver

    def _set_resolver(self, value):
        self._resolver = value

    def _del_resolver(self):
        del self._resolver

    resolver = property(_get_resolver, _set_resolver, _del_resolver)

    def _get_threadpool(self):
        if self._threadpool is None:
            if self.threadpool_class is not None:
                self.threadpool_class = _import(self.threadpool_class)
                self._threadpool = self.threadpool_class(self.threadpool_size, hub=self)
        return self._threadpool

    def _set_threadpool(self, value):
        self._threadpool = value

    def _del_threadpool(self):
        del self._threadpool

    threadpool = property(_get_threadpool, _set_threadpool, _del_threadpool)


class Waiter(object):
    """
    A low level communication utility for greenlets.

    Waiter is a wrapper around greenlet's ``switch()`` and ``throw()`` calls that makes them somewhat safer:

    * switching will occur only if the waiting greenlet is executing :meth:`get` method currently;
    * any error raised in the greenlet is handled inside :meth:`switch` and :meth:`throw`
    * if :meth:`switch`/:meth:`throw` is called before the receiver calls :meth:`get`, then :class:`Waiter`
      will store the value/exception. The following :meth:`get` will return the value/raise the exception.

    The :meth:`switch` and :meth:`throw` methods must only be called from the :class:`Hub` greenlet.
    The :meth:`get` method must be called from a greenlet other than :class:`Hub`.

        >>> result = Waiter()
        >>> timer = get_hub().loop.timer(0.1)
        >>> timer.start(result.switch, 'hello from Waiter')
        >>> result.get() # blocks for 0.1 seconds
        'hello from Waiter'

    If switch is called before the greenlet gets a chance to call :meth:`get` then
    :class:`Waiter` stores the value.

        >>> result = Waiter()
        >>> timer = get_hub().loop.timer(0.1)
        >>> timer.start(result.switch, 'hi from Waiter')
        >>> sleep(0.2)
        >>> result.get() # returns immediatelly without blocking
        'hi from Waiter'

    .. warning::

        This a limited and dangerous way to communicate between
        greenlets. It can easily leave a greenlet unscheduled forever
        if used incorrectly. Consider using safer classes such as
        :class:`gevent.event.Event`, :class:`gevent.event.AsyncResult`,
        or :class:`gevent.queue.Queue`.
    """

    __slots__ = ['hub', 'greenlet', 'value', '_exception']

    def __init__(self, hub=None):
        if hub is None:
            self.hub = get_hub()
        else:
            self.hub = hub
        self.greenlet = None
        self.value = None
        self._exception = _NONE

    def clear(self):
        self.greenlet = None
        self.value = None
        self._exception = _NONE

    def __str__(self):
        if self._exception is _NONE:
            return '<%s greenlet=%s>' % (type(self).__name__, self.greenlet)
        elif self._exception is None:
            return '<%s greenlet=%s value=%r>' % (type(self).__name__, self.greenlet, self.value)
        else:
            return '<%s greenlet=%s exc_info=%r>' % (type(self).__name__, self.greenlet, self.exc_info)

    def ready(self):
        """Return true if and only if it holds a value or an exception"""
        return self._exception is not _NONE

    def successful(self):
        """Return true if and only if it is ready and holds a value"""
        return self._exception is None

    @property
    def exc_info(self):
        "Holds the exception info passed to :meth:`throw` if :meth:`throw` was called. Otherwise ``None``."
        if self._exception is not _NONE:
            return self._exception

    def switch(self, value=None):
        """Switch to the greenlet if one's available. Otherwise store the value."""
        greenlet = self.greenlet
        if greenlet is None:
            self.value = value
            self._exception = None
        else:
            assert getcurrent() is self.hub, "Can only use Waiter.switch method from the Hub greenlet"
            switch = greenlet.switch
            try:
                switch(value)
            except:
                self.hub.handle_error(switch, *sys.exc_info())

    def switch_args(self, *args):
        return self.switch(args)

    def throw(self, *throw_args):
        """Switch to the greenlet with the exception. If there's no greenlet, store the exception."""
        greenlet = self.greenlet
        if greenlet is None:
            self._exception = throw_args
        else:
            assert getcurrent() is self.hub, "Can only use Waiter.switch method from the Hub greenlet"
            throw = greenlet.throw
            try:
                throw(*throw_args)
            except:
                self.hub.handle_error(throw, *sys.exc_info())

    def get(self):
        """If a value/an exception is stored, return/raise it. Otherwise until switch() or throw() is called."""
        if self._exception is not _NONE:
            if self._exception is None:
                return self.value
            else:
                getcurrent().throw(*self._exception)
        else:
            if self.greenlet is not None:
                raise ConcurrentObjectUseError('This Waiter is already used by %r' % (self.greenlet, ))
            self.greenlet = getcurrent()
            try:
                return self.hub.switch()
            finally:
                self.greenlet = None

    def __call__(self, source):
        if source.exception is None:
            self.switch(source.value)
        else:
            self.throw(source.exception)

    # can also have a debugging version, that wraps the value in a tuple (self, value) in switch()
    # and unwraps it in wait() thus checking that switch() was indeed called


class _MultipleWaiter(Waiter):
    """
    An internal extension of Waiter that can be used if multiple objects
    must be waited on, and there is a chance that in between waits greenlets
    might be switched out. All greenlets that switch to this waiter
    will have their value returned.

    This does not handle exceptions or throw methods.
    """
    _DEQUE = None
    __slots__ = ['_values']

    def __init__(self, *args, **kwargs):
        Waiter.__init__(self, *args, **kwargs)
        self._values = self._deque()

    @classmethod
    def _deque(cls):
        if cls._DEQUE is None:
            from collections import deque
            cls._DEQUE = deque
        return cls._DEQUE()

    def switch(self, value):
        self._values.append(value)
        Waiter.switch(self, True)

    def get(self):
        if not self._values:
            Waiter.get(self)
            Waiter.clear(self)

        return self._values.popleft()


def iwait(objects, timeout=None, count=None):
    """
    Iteratively yield *objects* as they are ready, until all (or *count*) are ready
    or *timeout* expired.

    :param objects: A sequence (supporting :func:`len`) containing objects
        implementing the wait protocol (rawlink() and unlink()).
    :keyword int count: If not `None`, then a number specifying the maximum number
        of objects to wait for. If ``None`` (the default), all objects
        are waited for.
    :keyword float timeout: If given, specifies a maximum number of seconds
        to wait. If the timeout expires before the desired waited-for objects
        are available, then this method returns immediately.

    .. seealso:: :func:`wait`
    """
    # QQQ would be nice to support iterable here that can be generated slowly (why?)
    if objects is None:
        yield get_hub().join(timeout=timeout)
        return

    count = len(objects) if count is None else min(count, len(objects))
    waiter = _MultipleWaiter()
    switch = waiter.switch

    if timeout is not None:
        timer = get_hub().loop.timer(timeout, priority=-1)
        timer.start(switch, _NONE)

    try:
        for obj in objects:
            obj.rawlink(switch)

        for _ in xrange(count):
            item = waiter.get()
            waiter.clear()
            if item is _NONE:
                return
            yield item
    finally:
        if timeout is not None:
            timer.stop()
        for obj in objects:
            unlink = getattr(obj, 'unlink', None)
            if unlink:
                try:
                    unlink(switch)
                except:
                    traceback.print_exc()


def wait(objects=None, timeout=None, count=None):
    """
    Wait for ``objects`` to become ready or for event loop to finish.

    If ``objects`` is provided, it must be a list containing objects
    implementing the wait protocol (rawlink() and unlink() methods):

    - :class:`gevent.Greenlet` instance
    - :class:`gevent.event.Event` instance
    - :class:`gevent.lock.Semaphore` instance
    - :class:`gevent.subprocess.Popen` instance

    If ``objects`` is ``None`` (the default), ``wait()`` blocks until
    the current event loop has nothing to do (or until ``timeout`` passes):

    - all greenlets have finished
    - all servers were stopped
    - all event loop watchers were stopped.

    If ``count`` is ``None`` (the default), wait for all ``objects``
    to become ready.

    If ``count`` is a number, wait for (up to) ``count`` objects to become
    ready. (For example, if count is ``1`` then the function exits
    when any object in the list is ready).

    If ``timeout`` is provided, it specifies the maximum number of
    seconds ``wait()`` will block.

    Returns the list of ready objects, in the order in which they were
    ready.

    .. seealso:: :func:`iwait`
    """
    if objects is None:
        return get_hub().join(timeout=timeout)
    return list(iwait(objects, timeout, count))


class linkproxy(object):
    __slots__ = ['callback', 'obj']

    def __init__(self, callback, obj):
        self.callback = callback
        self.obj = obj

    def __call__(self, *args):
        callback = self.callback
        obj = self.obj
        self.callback = None
        self.obj = None
        callback(obj)


class _NONE(object):
    "A special thingy you must never pass to any of gevent API"
    __slots__ = []

    def __repr__(self):
        return '<_NONE>'

_NONE = _NONE()
