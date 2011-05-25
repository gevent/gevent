# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.

import sys
import os
import traceback
from gevent import core


__all__ = ['getcurrent',
           'GreenletExit',
           'spawn_raw',
           'sleep',
           'kill',
           'signal',
           'fork',
           'get_hub',
           'Hub',
           'Waiter']


def __import_py_magic_greenlet():
    try:
        from py.magic import greenlet
        return greenlet
    except ImportError:
        pass

try:
    greenlet = __import__('greenlet').greenlet
except ImportError:
    greenlet = __import_py_magic_greenlet()
    if greenlet is None:
        raise

getcurrent = greenlet.getcurrent
GreenletExit = greenlet.GreenletExit

thread = __import__('thread')
threadlocal = thread._local
_threadlocal = threadlocal()
_threadlocal.Hub = None
try:
    _original_fork = os.fork
except AttributeError:
    _original_fork = None
    __all__.remove('fork')
get_ident = thread.get_ident
MAIN_THREAD = get_ident()


def _switch_helper(function, args, kwargs):
    # work around the fact that greenlet.switch does not support keyword args
    return function(*args, **kwargs)


def spawn_raw(function, *args, **kwargs):
    hub = get_hub()
    if kwargs:
        g = greenlet(_switch_helper, hub)
        hub.loop.run_callback(g.switch, function, args, kwargs)
    else:
        g = greenlet(function, hub)
        hub.loop.run_callback(g.switch, *args)
    return g


def sleep(seconds=0):
    """Put the current greenlet to sleep for at least *seconds*.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling sleep with *seconds* of 0 is the canonical way of
    expressing a cooperative yield.
    """
    if not seconds >= 0:
        raise IOError(22, 'Invalid argument')
    hub = get_hub()
    hub.wait(hub.loop.timer(seconds))


def kill(greenlet, exception=GreenletExit):
    """Kill greenlet asynchronously. The current greenlet is not unscheduled.

    Note, that :meth:`gevent.Greenlet.kill` method does the same and more. However,
    MAIN greenlet - the one that exists initially - does not have ``kill()`` method
    so you have to use this function.
    """
    if not greenlet.dead:
        get_hub().loop.run_callback(greenlet.throw, exception)


class Signal(object):

    def __init__(self, signalnum):
        self.hub = get_hub()
        self.watcher = self.hub.loop.signal(signalnum)
        self._unref = 0

    def start(self, handler, *args, **kwargs):
        self.watcher.start(spawn_raw, self.handle, handler, args, kwargs)
        if self._unref == 0:
            self.hub.loop.unref()
            self._unref = 1

    def cancel(self):
        self.watcher.stop()
        if self._unref == 1:
            self.hub.loop.ref()
            self._unref = 0

    def handle(self, handler, args, kwargs):
        try:
            handler(*args, **kwargs)
        except:
            self.hub.handle_error(None, *sys.exc_info())
        if not self.watcher.active and self._unref == 1:
            self.hub.loop.ref()
            self._unref = 0


def signal(signalnum, handler, *args, **kwargs):
    obj = Signal(signalnum)
    obj.start(handler, *args, **kwargs)
    return obj


if _original_fork is not None:

    def fork():
        result = _original_fork()
        get_hub().loop.reinit()
        return result


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
    """Return the hub for the current thread.

    If hub does not exists in the current thread, the new one is created with call to :meth:`get_hub_class`.
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
        error = ImportError('Cannot import from empty list: %r' % (path, ))
        for item in path:
            try:
                return _import(item)
            except ImportError, ex:
                error = ex
        raise error
    if not isinstance(path, basestring):
        return path
    module, item = path.rsplit('.', 1)
    x = __import__(module)
    for attr in path.split('.')[1:]:
        try:
            x = getattr(x, attr)
        except AttributeError:
            raise ImportError('cannot import name %r from %r' % (attr, x))
    return x


class Hub(greenlet):
    """A greenlet that runs the event loop.

    It is created automatically by :func:`get_hub`.
    """

    SYSTEM_ERROR = (KeyboardInterrupt, SystemExit, SystemError)
    NOT_ERROR = (GreenletExit, )
    loop_class = 'gevent.core.loop'
    resolver_class = ['gevent.resolver_ares.Resolver',
                      'gevent.socket.BlockingResolver']
    pformat = 'pprint.pformat'

    def __init__(self, loop=None, default=None):
        greenlet.__init__(self)
        if hasattr(loop, 'run'):
            if default is not None:
                raise TypeError("Unexpected argument: 'default'")
            self.loop = loop
        else:
            if default is None:
                default = get_ident() == MAIN_THREAD
            loop_class = _import(self.loop_class)
            self.loop = loop_class(flags=loop, default=default)
        self._resolver = None
        self.pformat = _import(self.pformat)

    def handle_error(self, where, type, value, tb):
        if not issubclass(type, self.NOT_ERROR):
            traceback.print_exception(type, value, tb)
        del tb
        if where is None or issubclass(type, self.SYSTEM_ERROR):
            current = getcurrent()
            if current is self or current is self.parent:
                self.parent.throw(type, value)
            else:
                self.loop.run_callback(self.parent.throw, type, value)
        else:
            if not isinstance(where, str):
                try:
                    where = self.pformat(where)
                except:
                    traceback.print_exc()
                    where = repr(where)
            sys.stderr.write('Ignoring %s in %s\n\n' % (getattr(type, '__name__', 'exception'), where, ))

    def switch(self):
        cur = getcurrent()
        assert cur is not self, 'Impossible to call blocking function in the event loop callback'
        exc_type, exc_value = sys.exc_info()[:2]
        try:
            switch_out = getattr(cur, 'switch_out', None)
            if switch_out is not None:
                try:
                    switch_out()
                except:
                    self.handle_error(switch_out, *sys.exc_info())
            sys.exc_clear()
            return greenlet.switch(self)
        finally:
            core.set_exc_info(exc_type, exc_value)

    def wait(self, watcher):
        watcher.start(getcurrent().switch, watcher, None)
        try:
            result = self.switch()
            assert isinstance(result, tuple) and result[0] is watcher, 'Invalid switch into %s: %r' % (getcurrent(), result)
            return result
        finally:
            watcher.stop()

    def cancel_wait(self, watcher, error):
        self.loop.run_callback(self._cancel_wait, watcher, error)

    def _cancel_wait(self, watcher, error):
        if watcher.active:
            switch = watcher.callback
            if switch is not None:
                greenlet = getattr(switch, '__self__', None)
                if greenlet is not None:
                    greenlet.throw(error)

    def run(self):
        global _threadlocal
        assert self is getcurrent(), 'Do not call Hub.run() directly'
        try:
            self.loop.error_handler = self
            self.loop.run()
        finally:
            if _threadlocal.__dict__.get('hub') is self:
                _threadlocal.__dict__.pop('hub')
            self.loop.error_handler = None  # break the ref cycle
        # this function must never return, as it will cause switch() in the parent greenlet
        # to return an unexpected value
        raise LoopExit

    def join(self):
        """Wait for the event loop to finish. Exits only when there are
        no more spawned greenlets, started servers, active timeouts or watchers.
        """
        assert getcurrent() is self.parent, "only possible from MAIN greenlet"
        if not self or self.dead:
            if _threadlocal.__dict__.get('hub') is self:
                _threadlocal.__dict__.pop('hub')
            self.run = None
        else:
            try:
                self.switch()
            except LoopExit:
                pass
        self.loop.error_handler = None  # break the ref cycle

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


class LoopExit(Exception):
    pass


class Waiter(object):
    """A low level communication utility for greenlets.

    Wrapper around greenlet's ``switch()`` and ``throw()`` calls that makes them somewhat safer:

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

        This a limited and dangerous way to communicate between greenlets. It can easily
        leave a greenlet unscheduled forever if used incorrectly. Consider using safer
        :class:`Event`/:class:`AsyncResult`/:class:`Queue` classes.
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
        if self.greenlet is None:
            self.value = value
            self._exception = None
        else:
            assert getcurrent() is self.hub, "Can only use Waiter.switch method from the Hub greenlet"
            try:
                self.greenlet.switch(value)
            except:
                self.hub.handle_error(self.greenlet.switch, *sys.exc_info())

    def switch_args(self, *args):
        return self.switch(args)

    def throw(self, *throw_args):
        """Switch to the greenlet with the exception. If there's no greenlet, store the exception."""
        if self.greenlet is None:
            self._exception = throw_args
        else:
            assert getcurrent() is self.hub, "Can only use Waiter.switch method from the Hub greenlet"
            try:
                self.greenlet.throw(*throw_args)
            except:
                self.hub.handle_error(self.greenlet.throw, *sys.exc_info())

    def get(self):
        """If a value/an exception is stored, return/raise it. Otherwise until switch() or throw() is called."""
        if self._exception is not _NONE:
            if self._exception is None:
                return self.value
            else:
                getcurrent().throw(*self._exception)
        else:
            assert self.greenlet is None, 'This Waiter is already used by %r' % (self.greenlet, )
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


class _NONE(object):
    "A special thingy you must never pass to any of gevent API"
    __slots__ = []

    def __repr__(self):
        return '<_NONE>'

_NONE = _NONE()
