# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

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


try:
    greenlet = __import__('greenlet').greenlet
except ImportError:
    try:
        from py.magic import greenlet
    except ImportError:
        raise ImportError('gevent requires greenlet library: http://pypi.python.org/pypi/greenlet/')

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
        core.active_event(g.switch, function, args, kwargs)
        return g
    else:
        g = greenlet(function, get_hub())
        core.active_event(g.switch, *args)
        return g


def sleep(seconds=0):
    """Put the current greenlet to sleep for at least *seconds*.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling sleep with *seconds* of 0 is the canonical way of
    expressing a cooperative yield.
    """
    unique_mark = object()
    t = core.timer(seconds, getcurrent().switch, unique_mark)
    try:
        switch_result = get_hub().switch()
        assert switch_result is unique_mark, 'Invalid switch into sleep(): %r' % (switch_result, )
    except:
        t.cancel()
        raise


def kill(greenlet, exception=GreenletExit):
    """Kill greenlet asynchronously. The current greenlet is not unscheduled.

    Note, that :meth:`gevent.Greenlet.kill` method does the same and more. However,
    MAIN greenlet - the one that exists initially - does not have ``kill()`` method
    so you have to use this function.
    """
    if not greenlet.dead:
        core.active_event(greenlet.throw, exception)


def _wrap_signal_handler(handler, args, kwargs):
    try:
        handler(*args, **kwargs)
    except:
        core.active_event(MAIN.throw, *sys.exc_info())

def signal(signalnum, handler, *args, **kwargs):
    return core.signal(signalnum, lambda : spawn_raw(_wrap_signal_handler, handler, args, kwargs))


if _original_fork is not None:

    def fork():
        result = _original_fork()
        core.reinit()
        return result


def shutdown():
    """Cancel our CTRL-C handler and wait for core.dispatch() to return."""
    global _threadlocal
    hub = _threadlocal.__dict__.get('hub')
    if hub is not None and not hub.dead:
        hub.shutdown()


def get_hub():
    global _threadlocal
    try:
        return _threadlocal.hub
    except AttributeError:
        try:
            hubtype = _threadlocal.Hub
        except AttributeError:
            # do not pretend to support multiple threads because it's not implemented properly by core.pyx
            # this may change in the future, although currently I don't have a strong need for this
            raise NotImplementedError('gevent is only usable from a single thread')
        if hubtype is None:
            hubtype = Hub
        hub = _threadlocal.hub = hubtype()
        return hub


class Hub(greenlet):
    """A greenlet that runs the event loop.

    It is created automatically by :func:`get_hub`.
    """

    def __init__(self):
        greenlet.__init__(self)
        self.keyboard_interrupt_signal = None

    def switch(self):
        cur = getcurrent()
        assert cur is not self, 'Cannot switch to MAINLOOP from MAINLOOP'
        switch_out = getattr(cur, 'switch_out', None)
        if switch_out is not None:
            try:
                switch_out()
            except:
                traceback.print_exc()
        return greenlet.switch(self)

    def run(self):
        global _threadlocal
        assert self is getcurrent(), 'Do not call run() directly'
        self.keyboard_interrupt_signal = signal(2, core.active_event, MAIN.throw, KeyboardInterrupt)
        try:
            loop_count = 0
            while True:
                try:
                    result = core.dispatch()
                except IOError, ex:
                    loop_count += 1
                    if loop_count > 15:
                        raise
                    sys.stderr.write('Restarting gevent.core.dispatch() after an error [%s]: %s\n' % (loop_count, ex))
                    continue
                raise DispatchExit(result)
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
        core.dns_shutdown()
        try:
            self.switch()
        except DispatchExit, ex:
            if ex.code == 1:
                return
            raise


class DispatchExit(Exception):

    def __init__(self, code):
        self.code = code
        Exception.__init__(self, code)


class Waiter(object):
    """A low level synchronization class.

    Wrapper around greenlet's ``switch()`` and ``throw()`` calls that makes them safe:

    * switching will occur only if the waiting greenlet is executing :meth:`wait`
      method currently. Otherwise, :meth:`switch` and :meth:`throw` are no-ops.
    * any error raised in the greenlet is handled inside :meth:`switch` and :meth:`throw`

    The :meth:`switch` and :meth:`throw` methods must only be called from the :class:`Hub` greenlet.
    The :meth:`wait` method must be called from a greenlet other than :class:`Hub`.
    """
    __slots__ = ['greenlet']

    def __init__(self):
        self.greenlet = None

    def __repr__(self):
        if self.waiting:
            waiting = ' waiting'
        else:
            waiting = ''
        return '<%s at %s%s greenlet=%r>' % (type(self).__name__, hex(id(self)), waiting, self.greenlet)

    def __str__(self):
        """
        >>> print Waiter()
        <Waiter greenlet=None>
        """
        if self.waiting:
            waiting = ' waiting'
        else:
            waiting = ''
        return '<%s%s greenlet=%s>' % (type(self).__name__, waiting, self.greenlet)

    def __nonzero__(self):
        return self.greenlet is not None

    @property
    def waiting(self):
        return self.greenlet is not None

    def switch(self, value=None):
        """Wake up the greenlet that is calling wait() currently (if there is one).
        Can only be called from Hub's greenlet.
        """
        assert getcurrent() is get_hub(), "Can only use Waiter.switch method from the mainloop"
        if self.greenlet is not None:
            try:
                self.greenlet.switch(value)
            except:
                traceback.print_exc()

    def throw(self, *throw_args):
        """Make greenlet calling wait() wake up (if there is a wait()).
        Can only be called from Hub's greenlet.
        """
        assert getcurrent() is get_hub(), "Can only use Waiter.switch method from the mainloop"
        if self.greenlet is not None:
            try:
                self.greenlet.throw(*throw_args)
            except:
                traceback.print_exc()

    # XXX should be renamed to get() ? and the whole class is called Receiver?
    def wait(self):
        """Wait until switch() or throw() is called.
        """
        assert self.greenlet is None, 'This Waiter is already used by %r' % (self.greenlet, )
        self.greenlet = getcurrent()
        try:
            return get_hub().switch()
        finally:
            self.greenlet = None

    # can also have a debugging version, that wraps the value in a tuple (self, value) in switch()
    # and unwraps it in wait() thus checking that switch() was indeed called

