from gevent import core
from gevent.hub import getcurrent

__all__ = ['Timeout',
           'with_timeout']


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


# how about returning Timeout instance ?
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


_NONE = object()

