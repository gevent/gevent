import sys
import os
import traceback
import _socket # for timeout
from gevent import core


__all__ = ['getcurrent',
           'sleep',
           'spawn',
           'spawn_later',
           'kill',
           'killall',
           'join',
           'joinall',
           'Timeout',
           'with_timeout',
           'signal',
           'fork',
           'shutdown']


try:
    from py.magic import greenlet
    Greenlet = greenlet
except ImportError:
    greenlet = __import__('greenlet')
    Greenlet = greenlet.greenlet

getcurrent = greenlet.getcurrent
GreenletExit = greenlet.GreenletExit
MAIN = greenlet.getcurrent()

thread = __import__('thread')
threadlocal = thread._local
_threadlocal = threadlocal()
_threadlocal.Hub = None
_original_fork = os.fork


def sleep(seconds=0):
    """Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling sleep with *seconds* of 0 is the canonical way of
    expressing a cooperative yield. For example, if one is looping over a
    large list performing an expensive calculation without calling any socket
    methods, it's a good idea to call ``sleep(0)`` occasionally; otherwise
    nothing else will run.
    """
    unique_mark = object()
    t = core.timer(seconds, getcurrent().switch, unique_mark)
    try:
        switch_result = get_hub().switch()
        assert switch_result is unique_mark, 'Invalid switch into sleep(): %r' % (switch_result, )
    finally:
        t.cancel()


def _switch_helper(function, args, kwargs):
    # work around the fact that greenlet.switch does not support keyword args
    return function(*args, **kwargs)


def spawn(function, *args, **kwargs):
    if kwargs:
        g = Greenlet(_switch_helper, get_hub().greenlet)
        core.active_event(g.switch, function, args, kwargs)
        return g
    else:
        g = Greenlet(function, get_hub().greenlet)
        core.active_event(g.switch, *args)
        return g


def spawn_later(seconds, function, *args, **kwargs):
    if kwargs:
        g = Greenlet(_switch_helper, get_hub().greenlet)
        core.timer(seconds, g.switch, function, args, kwargs)
        return g
    else:
        g = Greenlet(function, get_hub().greenlet)
        core.timer(seconds, g.switch, *args)
        return g


def _kill(greenlet, exception, waiter):
    try:
        greenlet.throw(exception)
    except:
        traceback.print_exc()
    waiter.switch()


def kill(greenlet, exception=GreenletExit, block=False, polling_period=0.2):
    """Kill greenlet with exception (GreenletExit by default).
    Wait for it to die if block is true.
    """
    if not greenlet.dead:
        waiter = Waiter()
        core.active_event(_kill, greenlet, exception, waiter)
        if block:
            waiter.wait()
            join(greenlet, polling_period=polling_period)


def _killall(greenlets, exception, waiter):
    diehards = []
    for g in greenlets:
        if not g.dead:
            try:
                g.throw(exception)
            except:
                traceback.print_exc()
            if not g.dead:
                diehards.append(g)
    waiter.switch(diehards)


def killall(greenlets, exception=GreenletExit, block=False, polling_period=0.2):
    """Kill all the greenlets with exception (GreenletExit by default).
    Wait for them to die if block is true.
    """
    waiter = Waiter()
    core.active_event(_killall, greenlets, exception, waiter)
    if block:
        alive = waiter.wait()
        if alive:
            joinall(alive, polling_period=polling_period)


def join(greenlet, polling_period=0.2):
    """Wait for a greenlet to finish by polling its status"""
    delay = 0.002
    while not greenlet.dead:
        delay = min(polling_period, delay*2)
        sleep(delay)


def joinall(greenlets, polling_period=0.2):
    """Wait for the greenlets to finish by polling their status"""
    current = 0
    while current < len(greenlets) and greenlets[current].dead:
        current += 1
    delay = 0.002
    while current < len(greenlets):
        delay = min(polling_period, delay*2)
        sleep(delay)
        while current < len(greenlets) and greenlets[current].dead:
            current += 1


try:
    BaseException
except NameError: # Python < 2.5
    class BaseException:
        # not subclassing from object() intentionally, because in
        # that case "raise Timeout" fails with TypeError.
        pass


class Timeout(BaseException):
    """Raise an exception in the current greenlet after timeout.

    timeout = Timeout(seconds[, exception])
    try:
        ... code block ...
    finally:
        timeout.cancel()

    Assuming code block is yielding (i.e. gives up control to the hub),
    an exception will be raised if code block has been running for more
    than `seconds` seconds. By default (or when exception is None), the
    Timeout instance itself is raised. If exception is provided, then it
    is raised instead.

    For Python starting with 2.5 'with' statement can be used:

    with Timeout(seconds[, exception]) as timeout:
        ... code block ...

    This is equivalent to try/finally block above with one additional feature:
    if exception is False, the timeout is still raised, but context manager
    suppresses it, so surrounding code won't see it.

    This is handy for adding a timeout feature to the functions that don't
    implement it themselves:

    data = None
    with Timeout(5, False):
        data = mysock.makefile().readline()
    if data is None:
        # 5 seconds passed without reading a line
    else:
        # a line was read within 5 seconds

    Note that, if readline() catches BaseException (or everything with 'except:'),
    then your timeout is screwed.

    When catching timeouts, keep in mind that the one you catch maybe not the
    one you have set; if you going to silent a timeout, always check that it's
    the one you need:

    timeout = Timeout(1)
    try:
        ...
    except Timeout, t:
        if t is not timeout:
            raise # not my timeout
    """

    def __init__(self, seconds=None, exception=None):
        if seconds is None: # "fake" timeout (never expires)
            self.exception = None
            self.timer = None
        elif exception is None or exception is False: # timeout that raises self
            self.exception = exception
            self.timer = core.timer(seconds, getcurrent().throw, self)
        else: # regular timeout with user-provided exception
            self.exception = exception
            self.timer = core.timer(seconds, getcurrent().throw, exception)

    @property
    def pending(self):
        if self.timer is not None:
            return self.timer.pending
        else:
            return False

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()

    def __repr__(self):
        try:
            classname = self.__class__.__name__
        except AttributeError: # Python < 2.5
            classname = 'Timeout'
        if self.exception is None:
            return '<%s at %s timer=%s>' % (classname, hex(id(self)), self.timer)
        else:
            return '<%s at %s timer=%s exception=%s>' % (classname, hex(id(self)), self.timer, self.exception)

    def __str__(self):
        """
        >>> raise Timeout
        Traceback (most recent call last):
            ...
        Timeout
        """
        if self.exception is None:
            return ''
        elif self.exception is False:
            return '(silent)'
        else:
            return str(self.exception)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        self.cancel()
        if value is self and self.exception is False:
            return True


# use this? less prone to errors (what if func has timeout_value argument or func is with_timeout itself?)
# def with_timeout(seconds, func[, args[, kwds[, timeout_value]]]):
# see what other similar standard library functions accept as params (start_new_thread, start new process)

class _NONE(object):
    __slots__ = []

_NONE = _NONE()


def with_timeout(seconds, func, *args, **kwds):
    """Wrap a call to some (yielding) function with a timeout; if the called
    function fails to return before the timeout, cancel it and return a flag
    value.

    seconds
      (int or float) seconds before timeout occurs
    func
      the callable to execute with a timeout; must be one of the functions
      that implicitly or explicitly yields
    \*args, \*\*kwds
      (positional, keyword) arguments to pass to *func*
    timeout_value=
      value to return if timeout occurs (default raise ``Timeout``)

    **Returns**:

    Value returned by *func* if *func* returns before *seconds*, else
    *timeout_value* if provided, else raise ``Timeout``

    **Raises**:

    Any exception raised by *func*, and ``Timeout`` if *func* times out
    and no ``timeout_value`` has been provided.

    **Example**::

      data = with_timeout(30, httpc.get, 'http://www.google.com/', timeout_value="")

    Here *data* is either the result of the ``get()`` call, or the empty string if
    it took too long to return. Any exception raised by the ``get()`` call is
    passed through to the caller.
    """
    # Recognize a specific keyword argument, while also allowing pass-through
    # of any other keyword arguments accepted by func. Use pop() so we don't
    # pass timeout_value through to func().
    timeout_value = kwds.pop("timeout_value", _NONE)
    timeout = Timeout(seconds)
    try:
        try:
            return func(*args, **kwds)
        except Timeout, t:
            if t is timeout and timeout_value is not _NONE:
                return timeout_value
            raise
    finally:
        timeout.cancel()


def signal(signalnum, handler, *args, **kwargs):
    def deliver_exception_to_MAIN():
        try:
            handler(*args, **kwargs)
        except:
            MAIN.throw(*sys.exc_info())
    return core.signal(signalnum, deliver_exception_to_MAIN)


def fork():
    result = _original_fork()
    core.reinit()
    return result


def shutdown():
    """Cancel our CTRL-C handler and wait for core.dispatch() to return."""
    global _threadlocal
    hub = _threadlocal.__dict__.get('hub')
    if hub is not None and not hub.greenlet.dead:
        hub.shutdown()


class Waiter(object):
    """A low level synchronization class.

    Wrapper around switch() and throw() calls that makes them safe:
    a) switching will occur only if the waiting greenlet is executing wait()
       method currently. Otherwise, switch() and throw() are no-ops.
    b) any error raised in the greenlet is handled inside switch() and throw()

    switch and throw methods must only be called from the mainloop greenlet.
    wait must be called from a greenlet other than mainloop.
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
        assert greenlet.getcurrent() is get_hub().greenlet, "Can only use Waiter.switch method from the mainloop"
        if self.greenlet is not None:
            try:
                self.greenlet.switch(value)
            except:
                traceback.print_exc()

    def throw(self, *throw_args):
        """Make greenlet calling wait() wake up (if there is a wait()).
        Can only be called from Hub's greenlet.
        """
        assert greenlet.getcurrent() is get_hub().greenlet, "Can only use Waiter.switch method from the mainloop"
        if self.greenlet is not None:
            try:
                self.greenlet.throw(*throw_args)
            except:
                traceback.print_exc()

    def wait(self):
        """Wait until switch() or throw() is called.
        """
        assert self.greenlet is None, 'This Waiter is already used by %r' % (self.greenlet, )
        self.greenlet = greenlet.getcurrent()
        try:
            return get_hub().switch()
        finally:
            self.greenlet = None


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


class Hub(object):

    def __init__(self):
        self.greenlet = Greenlet(self.run)
        self.keyboard_interrupt_signal = None

    @property
    def dead(self):
        return self.greenlet.dead

    def switch(self):
        cur = getcurrent()
        assert cur is not self.greenlet, 'Cannot switch to MAINLOOP from MAINLOOP'
        switch_out = getattr(cur, 'switch_out', None)
        if switch_out is not None:
            try:
                switch_out()
            except:
                traceback.print_exc()
        return self.greenlet.switch()

    def run(self):
        global _threadlocal
        assert self.greenlet is getcurrent(), 'Do not call run() directly'
        self.keyboard_interrupt_signal = signal(2, MAIN.throw, KeyboardInterrupt)
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
            if _threadlocal.__dict__.get('hub') is self:
                _threadlocal.__dict__.pop('hub')

    def shutdown(self):
        assert getcurrent() is MAIN, "Shutting down is only possible from MAIN greenlet"
        if self.keyboard_interrupt_signal is not None:
            self.keyboard_interrupt_signal.cancel()
            self.keyboard_interrupt_signal = None
        try:
            get_hub().switch()
        except DispatchExit, ex:
            if ex.code == 1:
                return
            raise


class DispatchExit(Exception):
    
    def __init__(self, code):
        self.code = code
        Exception.__init__(self, code)


def _wait_helper(ev, evtype):
    current, timeout_exc = ev.arg
    if evtype & core.EV_TIMEOUT:
        current.throw(timeout_exc)
    else:
        current.switch(ev)


def wait_reader(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.read(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        switch_result = get_hub().switch()
        assert evt is switch_result, 'Invalid switch into wait_reader(): %r' % (switch_result, )
    finally:
        evt.cancel()


def wait_writer(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.write(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        switch_result = get_hub().switch()
        assert evt is switch_result, 'Invalid switch into wait_writer(): %r' % (switch_result, )
    finally:
        evt.cancel()


