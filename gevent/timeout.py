# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

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
    timeout.start()
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
    timeout.start()
    try:
        ...
    except Timeout, t:
        if t is not timeout:
            raise # not my timeout
    """

    def __init__(self, seconds=None, exception=None):
        self.seconds = seconds
        self.exception = exception
        self.timer = None

    def start(self):
        if self.pending:
            raise AssertionError('%r is already started; to restart it, cancel it first' % self)
        if self.seconds is None: # "fake" timeout (never expires)
            self.timer = None
        elif self.exception is None or self.exception is False: # timeout that raises self
            self.timer = core.timer(self.seconds, getcurrent().throw, self)
        else: # regular timeout with user-provided exception
            self.timer = core.timer(self.seconds, getcurrent().throw, self.exception)

    @classmethod
    def start_new(cls, timeout=None, exception=None):
        if isinstance(timeout, Timeout):
            return timeout
        timeout = cls(timeout, exception)
        timeout.start()
        return timeout

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
        if self.pending:
            pending = ' pending'
        else:
            pending = ''
        if self.exception is None:
            exception = ''
        else:
            exception = ' exception=%r' % self.exception
        return '<%s at %s seconds=%s%s%s>' % (classname, hex(id(self)), self.seconds, exception, pending)

    def __str__(self):
        """
        >>> raise Timeout
        Traceback (most recent call last):
            ...
        Timeout
        """
        if self.seconds is None:
            return ''
        if self.seconds==1:
            s = ''
        else:
            s = 's'
        if self.exception is None:
            return '%s second%s' % (self.seconds, s)
        elif self.exception is False:
            return '%s second%s (silent)' % (self.seconds, s)
        else:
            return '%s second%s (%s)' % (self.seconds, s, self.exception)

    def __enter__(self):
        if self.timer is None:
            self.start()
        return self

    def __exit__(self, typ, value, tb):
        self.cancel()
        if value is self and self.exception is False:
            return True


def with_timeout(seconds, func, *args, **kwds):
    """Wrap a call to some (yielding) function with a timeout; if the called
    function fails to return before the timeout, cancel it and return a flag
    value, provided by 'timeout_value' keyword argument.

    If timeout expires but 'timeout_value' is not provided, raise Timeout.

    Keyword argument 'timeout_value', is not passed to func.
    """
    timeout_value = kwds.pop("timeout_value", _NONE)
    timeout = Timeout.start_new(seconds)
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

