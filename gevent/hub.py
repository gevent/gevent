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
           'shutdown',
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
MAIN = greenlet.getcurrent()

thread = __import__('thread')
threadlocal = thread._local
_threadlocal = threadlocal()
_threadlocal.Hub = None
try:
    _original_fork = os.fork
except AttributeError:
    _original_fork = None
    __all__.remove('fork')


def _switch_helper(function, args, kwargs):
    # work around the fact that greenlet.switch does not support keyword args
    return function(*args, **kwargs)


def spawn_raw(function, *args, **kwargs):
    if kwargs:
        g = greenlet(_switch_helper, get_hub())
        get_hub().reactor.active_event(g.switch, function, args, kwargs)
        return g
    else:
        g = greenlet(function, get_hub())
        get_hub().reactor.active_event(g.switch, *args)
        return g


def sleep(seconds=0):
    """Put the current greenlet to sleep for at least *seconds*.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling sleep with *seconds* of 0 is the canonical way of
    expressing a cooperative yield.
    """
    unique_mark = object()
    if not seconds >= 0:
        raise IOError(22, 'Invalid argument')
    timer = get_hub().reactor.timer(seconds, getcurrent().switch, unique_mark)
    try:
        switch_result = get_hub().switch()
        assert switch_result is unique_mark, 'Invalid switch into sleep(): %r' % (switch_result, )
    except:
        timer.cancel()
        raise


def kill(greenlet, exception=GreenletExit):
    """Kill greenlet asynchronously. The current greenlet is not unscheduled.

    Note, that :meth:`gevent.Greenlet.kill` method does the same and more. However,
    MAIN greenlet - the one that exists initially - does not have ``kill()`` method
    so you have to use this function.
    """
    if not greenlet.dead:
        get_hub().reactor.active_event(greenlet.throw, exception)


def _wrap_signal_handler(handler, args, kwargs):
    try:
        handler(*args, **kwargs)
    except:
        get_hub().reactor.active_event(MAIN.throw, *sys.exc_info())


def signal(signalnum, handler, *args, **kwargs):
    return get_hub().reactor.signal(signalnum, lambda: spawn_raw(_wrap_signal_handler, handler, args, kwargs))


if _original_fork is not None:

    def fork():
        result = _original_fork()
        get_hub().reactor.reinit()
        return result


def shutdown():
    """Cancel our CTRL-C handler and wait for core.dispatch() to return."""
    global _threadlocal
    hub = _threadlocal.__dict__.get('hub')
    if hub is not None:
        hub.shutdown()


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


def get_hub():
    """Return the hub for the current thread.

    If hub does not exists in the current thread, the new one is created with call to :meth:`get_hub_class`.
    """
    global _threadlocal
    try:
        return _threadlocal.hub
    except AttributeError:
        hubtype = get_hub_class()
        hub = _threadlocal.hub = hubtype()
        return hub


class Hub(greenlet):
    """A greenlet that runs the event loop.

    It is created automatically by :func:`get_hub`.
    """

    reactor_class = core.event_base

    def __init__(self, reactor=None):
        greenlet.__init__(self)
        self.keyboard_interrupt_signal = None
        if reactor is None:
            self.reactor = self.reactor_class()
        else:
            self.reactor = reactor

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
                    traceback.print_exc()
            sys.exc_clear()
            return greenlet.switch(self)
        finally:
            core.set_exc_info(exc_type, exc_value)

    def run(self):
        global _threadlocal
        assert self is getcurrent(), 'Do not call Hub.run() directly'
        try:
            self.keyboard_interrupt_signal = signal(2, self.reactor.active_event, MAIN.throw, KeyboardInterrupt)
        except IOError:
            pass  # no signal() on Windows
        try:
            loop_count = 0
            while True:
                try:
                    result = self.reactor.dispatch()
                except IOError, ex:
                    loop_count += 1
                    if loop_count > 15:
                        MAIN.throw(*sys.exc_info())
                    sys.stderr.write('Restarting gevent.core.dispatch() after an error [%s]: %s\n' % (loop_count, ex))
                    continue
                raise DispatchExit(result)
                # this function must never return, as it will cause switch() in MAIN to return an unexpected value
        finally:
            if self.keyboard_interrupt_signal is not None:
                self.keyboard_interrupt_signal.cancel()
                self.keyboard_interrupt_signal = None
            if _threadlocal.__dict__.get('hub') is self:
                _threadlocal.__dict__.pop('hub')

    def shutdown(self):
        assert getcurrent() is MAIN, "Shutting down is only possible from MAIN greenlet"
        if self.keyboard_interrupt_signal is not None:
            self.keyboard_interrupt_signal.cancel()
            self.keyboard_interrupt_signal = None
        dns = self.reactor.dns
        if dns is not None:
            dns.free()
        if not self or self.dead:
            if _threadlocal.__dict__.get('hub') is self:
                _threadlocal.__dict__.pop('hub')
            self.run = None
            return
        try:
            self.switch()
        except DispatchExit, ex:
            if ex.code == 1:  # no more events registered?
                return
            raise


class DispatchExit(Exception):

    def __init__(self, code):
        self.code = code
        Exception.__init__(self, code)


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
        >>> _ = get_hub().reactor.timer(0.1, result.switch, 'hello from Waiter')
        >>> result.get() # blocks for 0.1 seconds
        'hello from Waiter'

    If switch is called before the greenlet gets a chance to call :meth:`get` then
    :class:`Waiter` stores the value.

        >>> result = Waiter()
        >>> _ = get_hub().reactor.timer(0.1, result.switch, 'hi from Waiter')
        >>> sleep(0.2)
        >>> result.get() # returns immediatelly without blocking
        'hi from Waiter'

    .. warning::

        This a limited and dangerous way to communicate between greenlets. It can easily
        leave a greenlet unscheduled forever if used incorrectly. Consider using safer
        :class:`Event`/:class:`AsyncResult`/:class:`Queue` classes.
    """

    __slots__ = ['greenlet', 'value', '_exception']

    def __init__(self):
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
            assert getcurrent() is get_hub(), "Can only use Waiter.switch method from the Hub greenlet"
            try:
                self.greenlet.switch(value)
            except:
                traceback.print_exc()

    def switch_args(self, *args):
        return self.switch(args)

    def throw(self, *throw_args):
        """Switch to the greenlet with the exception. If there's no greenlet, store the exception."""
        if self.greenlet is None:
            self._exception = throw_args
        else:
            assert getcurrent() is get_hub(), "Can only use Waiter.switch method from the Hub greenlet"
            try:
                self.greenlet.throw(*throw_args)
            except:
                traceback.print_exc()

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
                return get_hub().switch()
            finally:
                self.greenlet = None

    # can also have a debugging version, that wraps the value in a tuple (self, value) in switch()
    # and unwraps it in wait() thus checking that switch() was indeed called


class _NONE(object):
    "A special thingy you must never pass to any of gevent API"
    __slots__ = []

    def __repr__(self):
        return '<_NONE>'

_NONE = _NONE()
