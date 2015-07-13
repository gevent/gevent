from __future__ import absolute_import
import os
import sys
from types import UnboundMethodType

from gevent._fileobjectcommon import cancel_wait_ex
from gevent._socket2 import _fileobject
from gevent._socket2 import _get_memory
from gevent.hub import get_hub, integer_types
from gevent.os import _read
from gevent.os import _write
from gevent.os import ignored_errors
from gevent.os import make_nonblocking
from gevent.socket import EBADF

from gevent._fileobjectposix import FileObjectPosix

try:
    from gevent._util import SocketAdapter__del__
except ImportError:
    SocketAdapter__del__ = None
    noop = None


class NA(object):

    def __repr__(self):
        return 'N/A'

NA = NA()

__all__ = ['FileObjectPosix', 'SocketAdapter']


class SocketAdapter(object):
    """Socket-like API on top of a file descriptor.

    The main purpose of it is to re-use _fileobject to create proper cooperative file objects
    from file descriptors on POSIX platforms.
    """

    def __init__(self, fileno, mode=None, close=True):
        if not isinstance(fileno, integer_types):
            raise TypeError('fileno must be int: %r' % fileno)
        self._fileno = fileno
        self._mode = mode or 'rb'
        self._close = close
        self._translate = 'U' in self._mode
        make_nonblocking(fileno)
        self._eat_newline = False
        self.hub = get_hub()
        io = self.hub.loop.io
        self._read_event = io(fileno, 1)
        self._write_event = io(fileno, 2)
        self._refcount = 1

    def __repr__(self):
        if self._fileno is None:
            return '<%s at 0x%x closed>' % (self.__class__.__name__, id(self))
        else:
            args = (self.__class__.__name__, id(self), getattr(self, '_fileno', NA), getattr(self, '_mode', NA))
            return '<%s at 0x%x (%r, %r)>' % args

    def makefile(self, *args, **kwargs):
        return _fileobject(self, *args, **kwargs)

    def fileno(self):
        result = self._fileno
        if result is None:
            raise IOError(EBADF, 'Bad file descriptor (%s object is closed)' % self.__class__.__name__)
        return result

    def detach(self):
        x = self._fileno
        self._fileno = None
        return x

    def _reuse(self):
        self._refcount += 1

    def _drop(self):
        self._refcount -= 1
        if self._refcount <= 0:
            self._realclose()

    def close(self):
        self._drop()

    def _realclose(self):
        self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        fileno = self._fileno
        if fileno is not None:
            self._fileno = None
            if self._close:
                os.close(fileno)

    def sendall(self, data):
        fileno = self.fileno()
        data_memory = _get_memory(data)
        bytes_total = len(data_memory)
        bytes_written = 0
        while True:
            try:
                bytes_written += _write(fileno, data_memory[bytes_written:])
            except (IOError, OSError) as ex:
                code = ex.args[0]
                if code not in ignored_errors:
                    raise
                sys.exc_clear()
            if bytes_written >= bytes_total:
                return
            self.hub.wait(self._write_event)

    def recv(self, size):
        while True:
            try:
                data = _read(self.fileno(), size)
            except (IOError, OSError) as ex:
                code = ex.args[0]
                if code not in ignored_errors:
                    raise
                sys.exc_clear()
            else:
                if not self._translate or not data:
                    return data
                if self._eat_newline:
                    self._eat_newline = False
                    if data.startswith(b'\n'):
                        data = data[1:]
                        if not data:
                            return self.recv(size)
                if data.endswith(b'\r'):
                    self._eat_newline = True
                return self._translate_newlines(data)
            self.hub.wait(self._read_event)

    def _translate_newlines(self, data):
        data = data.replace(b"\r\n", b"\n")
        data = data.replace(b"\r", b"\n")
        return data

    if not SocketAdapter__del__:

        def __del__(self, close=os.close):
            fileno = self._fileno
            if fileno is not None:
                close(fileno)

if SocketAdapter__del__:
    SocketAdapter.__del__ = UnboundMethodType(SocketAdapter__del__, None, SocketAdapter)
