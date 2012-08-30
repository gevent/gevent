"""
This module provides cooperative versions of os.read() and os.write().
On Posix platforms this uses non-blocking IO, on Windows a threadpool
is used.
"""

from __future__ import absolute_import

import os
import sys
from gevent.hub import get_hub, reinit
from gevent.socket import EAGAIN
import errno

try:
    import fcntl
except ImportError:
    fcntl = None

__implements__ = ['read', 'write', 'fork']
__all__ = __implements__

_read = os.read
_write = os.write


ignored_errors = [EAGAIN, errno.EINTR]
if sys.platform == 'darwin':
    # EINVAL sometimes happens on macosx without reason
    # http://code.google.com/p/gevent/issues/detail?id=148
    ignored_errors.append(errno.EINVAL)


def _map_errors(func, *args):
    """Map IOError to OSError."""
    try:
        return func(*args)
    except IOError, e:
        # IOError is structered like OSError in that it has two args: an error
        # number and a error string. So we can just re-raise OSError passing it
        # the IOError args. If at some point we want to catch other errors and
        # map those to OSError as well, we need to make sure that it follows
        # the OSError convention and it gets passed a valid error number and
        # error string.
        raise OSError(*e.args), None, sys.exc_info()[2]


def posix_read(fd, n):
    """Read up to `n` bytes from file descriptor `fd`. Return a string
    containing the bytes read. If end-of-file is reached, an empty string
    is returned."""
    hub, event = None, None
    while True:
        flags = _map_errors(fcntl.fcntl, fd, fcntl.F_GETFL, 0)
        if not flags & os.O_NONBLOCK:
            _map_errors(fcntl.fcntl, fd, fcntl.F_SETFL, flags|os.O_NONBLOCK)
        try:
            return _read(fd, n)
        except OSError, e:
            if e.errno not in ignored_errors:
                raise
            sys.exc_clear()
        finally:
            # Be sure to restore the fcntl flags before we switch into the hub.
            # Sometimes multiple file descriptors share the same fcntl flags
            # (e.g. when using ttys/ptys). Those other file descriptors are
            # impacted by our change of flags, so we should restore them
            # before any other code can possibly run.
            if not flags & os.O_NONBLOCK:
                _map_errors(fcntl.fcntl, fd, fcntl.F_SETFL, flags)
        if hub is None:
            hub = get_hub()
            event = hub.loop.io(fd, 1)
        hub.wait(event)


def posix_write(fd, buf):
    """Write bytes from buffer `buf` to file descriptor `fd`. Return the
    number of bytes written."""
    hub, event = None, None
    while True:
        flags = _map_errors(fcntl.fcntl, fd, fcntl.F_GETFL, 0)
        if not flags & os.O_NONBLOCK:
            _map_errors(fcntl.fcntl, fd, fcntl.F_SETFL, flags|os.O_NONBLOCK)
        try:
            return _write(fd, buf)
        except OSError, e:
            if e.errno not in ignored_errors:
                raise
            sys.exc_clear()
        finally:
            # See note in posix_read().
            if not flags & os.O_NONBLOCK:
                _map_errors(fcntl.fcntl, fd, fcntl.F_SETFL, flags)
        if hub is None:
            hub = get_hub()
            event = hub.loop.io(fd, 2)
        hub.wait(event)


def threadpool_read(fd, n):
    """Read up to `n` bytes from file descriptor `fd`. Return a string
    containing the bytes read. If end-of-file is reached, an empty string
    is returned."""
    return get_hub().threadpool.apply(_read, (fd, n))


def threadpool_write(fd, buf):
    """Write bytes from buffer `buf` to file descriptor `fd`. Return the
    number of bytes written."""
    return get_hub().threadpool.apply(_write, (fd, buf))


if fcntl is None:
    read = threadpool_read
    write = threadpool_write
else:
    read = posix_read
    write = posix_write


if hasattr(os, 'fork'):
    _fork = os.fork

    def fork():
        result = _fork()
        if not result:
            reinit()
        return result

else:
    __all__.remove('fork')
