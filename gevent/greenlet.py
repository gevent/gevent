import sys
import os
import traceback
from gevent import core


__all__ = ['getcurrent',
           'TimeoutError',
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


class TimeoutError(Exception):
    """Exception raised if an asynchronous operation times out"""


def spawn(function, *args, **kwargs):
    g = Greenlet(lambda : function(*args, **kwargs))
    g.parent = get_hub().greenlet
    core.active_event(g.switch)
    return g


def spawn_later(seconds, function, *args, **kwargs):
    g = Greenlet(lambda : function(*args, **kwargs))
    g.parent = get_hub().greenlet
    core.timer(seconds, g.switch)
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

    def switch(self, value=None):
        """Wake up the greenlet that is calling wait() currently (if there is one).
        Can only be called from get_hub().greenlet.
        """
        assert greenlet.getcurrent() is get_hub().greenlet
        if self.greenlet is not None:
            self.greenlet.switch(value)

    def throw(self, *throw_args):
        """Make greenlet calling wait() wake up (if there is a wait()).
        Can only be called from get_hub().greenlet.
        """
        assert greenlet.getcurrent() is get_hub().greenlet
        if self.greenlet is not None:
            self.greenlet.throw(*throw_args)

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
    assert hub.greenlet is not greenlet.getcurrent(), 'do not call blocking functions from the mainloop'
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


def wait_reader(fileno, timeout=-1, timeout_exc=TimeoutError):
    evt = core.read(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        returned_ev = get_hub().switch()
        assert evt is returned_ev, (evt, returned_ev)
    finally:
        evt.cancel()


def wait_writer(fileno, timeout=-1, timeout_exc=TimeoutError):
    evt = core.write(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        returned_ev = get_hub().switch()
        assert evt is returned_ev, (evt, returned_ev)
    finally:
        evt.cancel()


class _SilentException:
    """Used internally by Timeout as an exception which is not raise outside of with-block,
    and therefore is not visible by the user, unless she uses 'except:' construct.
    """


class Timeout(object):
    """Schedule an exception to be raised in the current greenlet (TimeoutError by default).

    Raise an exception in the block after timeout.

    with Timeout(seconds[, exc]) as timeout:
        ... code block ...

    Assuming code block is yielding (i.e. gives up control to the hub),
    an exception provided in `exc' argument will be raised
    (TimeoutError if `exc' is omitted). Although the timeout will be cancelled
    upon the block exit, it is also possible to cancel it inside the block explicitly,
    by calling timeout.cancel().

    When exc is None, code block is interrupted silently. (Which means that an
    exception that is not a subclass of Exception is raised but silented before exiting
    the block, thus giving the illusion that the block was interrupted. Catching
    all exceptions with "except:" will catch that exception too)
    """

    def __init__(self, seconds, exception=TimeoutError):
        if exception is None:
            exception = _SilentException()
        self.exception = exception
        if seconds is None:
            self.timeout = None
        else:
            self.timeout = core.timer(seconds, getcurrent().throw, exception)

    def cancel(self):
        if self.timeout is not None:
            self.timeout.cancel()

    def __repr__(self):
        return '<%s at %s timeout=%s exception=%s>' % (type(self).__name__, hex(id(self)), self.timeout, self.exception)

    def __enter__(self):
        return self

    def __exit__(self, typ, value, tb):
        self.cancel()
        if typ is _SilentException and value is self.exception:
            return True

# use this? less prone to errors (what if func has timeout_value argument or func is with_timeout itself?)
# def with_timeout(seconds, func[, args[, kwds[, timeout_value]]]):
# see what other similar standard library functions accept as params (start_new_thread, start new process)

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
      value to return if timeout occurs (default raise ``TimeoutError``)

    **Returns**:

    Value returned by *func* if *func* returns before *seconds*, else
    *timeout_value* if provided, else raise ``TimeoutError``

    **Raises**:

    Any exception raised by *func*, and ``TimeoutError`` if *func* times out
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
    has_timeout_value = "timeout_value" in kwds
    timeout_value = kwds.pop("timeout_value", None)
    error = TimeoutError()
    timeout = Timeout(seconds, error)
    try:
        try:
            return func(*args, **kwds)
        except TimeoutError, ex:
            if ex is error and has_timeout_value:
                return timeout_value
            raise
    finally:
        timeout.cancel()


_original_fork = os.fork

def fork():
    result = _original_fork()
    core.reinit()
    return result

