import sys
import os
import traceback
import _socket # for timeout
from gevent import core


__all__ = ['getcurrent',
           'Timeout',
           'spawn',
           'spawn_later',
           'kill',
           'killall',
           'sleep',
           'signal',
           'with_timeout',
           'fork']


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


def _switch_helper(function, args, kwargs):
    # work around the fact that greenlet.switch does not support keyword args
    return function(*args, **kwargs)


def spawn(function, *args, **kwargs):
    if kwargs:
        g = Greenlet(_switch_helper)
        g.parent = get_hub().greenlet
        core.active_event(g.switch, function, args, kwargs)
        return g
    else:
        g = Greenlet(function)
        g.parent = get_hub().greenlet
        core.active_event(g.switch, *args)
        return g


def spawn_later(seconds, function, *args, **kwargs):
    if kwargs:
        g = Greenlet(_switch_helper)
        g.parent = get_hub().greenlet
        core.timer(seconds, g.switch, function, args, kwargs)
        return g
    else:
        g = Greenlet(function)
        g.parent = get_hub().greenlet
        core.timer(seconds, g.switch, *args)
        return g


class Waiter(object):
    """A low level synchronization class.

    Wrapper around switch() and throw() calls that makes them safe.
    Switching will occur only if the waiting greenlet is executing wait()
    method currently. Otherwise, switch() and throw() are no-ops.
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

    @property
    def waiting(self):
        return self.greenlet is not None

    def switch(self, value=None):
        """Wake up the greenlet that is calling wait() currently (if there is one).
        Can only be called from get_hub().greenlet.
        """
        assert greenlet.getcurrent() is get_hub().greenlet
        if self.greenlet is not None:
            try:
                self.greenlet.switch(value)
            except:
                traceback.print_exc()

    def throw(self, *throw_args):
        """Make greenlet calling wait() wake up (if there is a wait()).
        Can only be called from get_hub().greenlet.
        """
        assert greenlet.getcurrent() is get_hub().greenlet
        if self.greenlet is not None:
            try:
                self.greenlet.throw(*throw_args)
            except:
                traceback.print_exc()

    def wait(self):
        """Wait until switch() or throw() is called.
        """
        assert self.greenlet is None, self.greenlet
        current = greenlet.getcurrent()
        assert current is not get_hub().greenlet
        self.greenlet = current
        try:
            return get_hub().switch()
        finally:
            self.greenlet = None


def _kill(greenlet, exception, waiter):
    try:
        greenlet.throw(exception)
    except:
        traceback.print_exc()
    waiter.switch()


def kill(greenlet, exception=GreenletExit, wait=False, polling_period=1):
    """Kill greenlet with exception (GreenletExit by default).
    Wait for it to die if wait=True.
    """
    waiter = Waiter()
    core.active_event(_kill, greenlet, exception, waiter)
    if wait:
        waiter.wait()
        while not greenlet.dead:
            sleep(polling_period)


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


def killall(greenlets, exception=GreenletExit, wait=False, polling_period=1):
    """Kill all the greenlets with exception (GreenletExit by default).
    Wait for them to die if wait=True.
    """
    waiter = Waiter()
    core.active_event(_killall, greenlets, exception, waiter)
    if wait:
        alive = waiter.wait()
        while alive:
            sleep(polling_period)
            while alive and alive[0].dead:
                del alive[0]


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
    hub = get_hub()
    t = core.timer(seconds, greenlet.getcurrent().switch)
    try:
        hub.switch()
    finally:
        t.cancel()


def signal(signalnum, handler, *args, **kwargs):
    def deliver_exception_to_MAIN():
        try:
            handler(*args, **kwargs)
        except:
            MAIN.throw(*sys.exc_info())
    return core.signal(signalnum, deliver_exception_to_MAIN)


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

    def switch(self):
        cur = getcurrent()
        assert cur is not self.greenlet, 'Cannot switch to MAINLOOP from MAINLOOP'
        switch_out = getattr(cur, 'switch_out', None)
        if switch_out is not None:
            try:
                switch_out()
            except:
                traceback.print_exc()
        if self.greenlet.dead:
            self.greenlet = Greenlet(self.run)
        return self.greenlet.switch()

    def run(self):
        if self.keyboard_interrupt_signal is None:
            self.keyboard_interrupt_signal = signal(2, MAIN.throw, KeyboardInterrupt)
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
            if result==1:
                raise DispatchExit('No events registered')
            raise DispatchExit('dispatch() exited with code %s' % (result, ))


class DispatchExit(Exception):
    pass


def _wait_helper(ev, evtype):
    current, timeout_exc = ev.arg
    if evtype & core.EV_TIMEOUT:
        current.throw(timeout_exc)
    else:
        current.switch(ev)


def wait_reader(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.read(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        returned_ev = get_hub().switch()
        assert evt is returned_ev, (evt, returned_ev)
    finally:
        evt.cancel()


def wait_writer(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.write(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        returned_ev = get_hub().switch()
        assert evt is returned_ev, (evt, returned_ev)
    finally:
        evt.cancel()


try:
    BaseException
except NameError: # Python < 2.5
    class BaseException:
        # not subclassing from object() intentionally, because in
        # that case "raise Timeout" fails with TypeError.
        pass


class _SilentException(BaseException):
    """Used internally by Timeout as an exception which is not raised outside of with-block,
    and therefore is not visible by the user, unless she uses "except:" construct.
    """
    __slots__ = []


class Timeout(BaseException):
    """Raise an exception in the current greenlet after timeout.

    timeout = Timeout(seconds[, exc])
    try:
        ... code block ...
    finally:
        timeout.cancel()

    By default, the Timeout instance itself is raised. If exc is provided, then
    it raised instead.

    For Python starting with 2.5 'with' statement can be used:

    with Timeout(seconds[, exc]) as timeout:
        ... code block ...

    Assuming code block is yielding (i.e. gives up control to the hub),
    an exception provided in `exc' argument will be raised. If exc is omitted
    or True, the timeout object itself is raised. Although the timeout will be
    cancelled upon the block exit, it is also possible to cancel it inside the
    block explicitly, by calling timeout.cancel().

    When exc is None, code block is interrupted "silently". Under the hood, an
    exception of a special type _SilentException (which is a subclass of BaseException
    but not Exception) is raised but silented before exiting the block
    in __exit__ method:

    data = None
    with Timeout(2, None):
        data = sock.recv(1024)
    if data is None:
        #  2 seconds passed without sock receiving anything
    else:
        # sock has received some data

    Note, that "except:" statement will still catch the exception thus breaking
    the illusion.
    """

    def __init__(self, seconds=None, exception=True):
        if seconds is None: # the timeout that never expires
            self.timer = None
            self.exception = None
        elif exception is True: # the timeout that raises self
            self.exception = exception
            self.timer = core.timer(seconds, getcurrent().throw, self)
        elif exception is None: # the timeout that interrupts the with-block "silently"
            self.exception = _SilentException()
            self.timer = core.timer(seconds, getcurrent().throw, self.exception)
        else: # the regular timeout with user-provided exception
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
        return '<%s at %s timer=%s exception=%s>' % (classname, hex(id(self)), self.timer, self.exception)

    def __str__(self):
        """
        >>> raise Timeout
        Traceback (most recent call last):
            ...
        Timeout
        """
        return ''

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        self.cancel()
        if typ is _SilentException and value is self.exception:
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


_original_fork = os.fork

def fork():
    result = _original_fork()
    core.reinit()
    return result

