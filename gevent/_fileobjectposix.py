from __future__ import absolute_import
import os
import io
from io import BufferedReader
from io import BufferedWriter
from io import BytesIO
from io import DEFAULT_BUFFER_SIZE
from io import RawIOBase
from io import TextIOWrapper
from io import UnsupportedOperation

from gevent._fileobjectcommon import cancel_wait_ex
from gevent.hub import get_hub
from gevent.os import _read
from gevent.os import _write
from gevent.os import ignored_errors
from gevent.os import make_nonblocking


class GreenFileDescriptorIO(RawIOBase):
    def __init__(self, fileno, mode='r', closefd=True):
        RawIOBase.__init__(self)
        self._closed = False
        self._closefd = closefd
        self._fileno = fileno
        make_nonblocking(fileno)
        self._readable = 'r' in mode
        self._writable = 'w' in mode
        self.hub = get_hub()
        io = self.hub.loop.io
        if self._readable:
            self._read_event = io(fileno, 1)
        else:
            self._read_event = None
        if self._writable:
            self._write_event = io(fileno, 2)
        else:
            self._write_event = None
        self._seekable = None

    def readable(self):
        return self._readable

    def writable(self):
        return self._writable

    def seekable(self):
        if self._seekable is None:
            try:
                os.lseek(self._fileno, 0, os.SEEK_CUR)
            except OSError:
                self._seekable = False
            else:
                self._seekable = True
        return self._seekable

    def fileno(self):
        return self._fileno

    @property
    def closed(self):
        return self._closed

    def close(self):
        if self._closed:
            return
        self.flush()
        self._closed = True
        if self._readable:
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        if self._writable:
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        fileno = self._fileno
        if self._closefd:
            self._fileno = None
            os.close(fileno)

    def read(self, n=1):
        if not self._readable:
            raise UnsupportedOperation('readinto')
        while True:
            try:
                return _read(self._fileno, n)
            except (IOError, OSError) as ex:
                if ex.args[0] not in ignored_errors:
                    raise
            self.hub.wait(self._read_event)

    def readall(self):
        ret = BytesIO()
        while True:
            data = self.read(DEFAULT_BUFFER_SIZE)
            if not data:
                break
            ret.write(data)
        return ret.getvalue()

    def readinto(self, b):
        data = self.read(len(b))
        n = len(data)
        try:
            b[:n] = data
        except TypeError as err:
            import array
            if not isinstance(b, array.array):
                raise err
            b[:n] = array.array(b'b', data)
        return n

    def write(self, b):
        if not self._writable:
            raise UnsupportedOperation('write')
        while True:
            try:
                return _write(self._fileno, b)
            except (IOError, OSError) as ex:
                if ex.args[0] not in ignored_errors:
                    raise
            self.hub.wait(self._write_event)

    def seek(self, offset, whence=0):
        return os.lseek(self._fileno, offset, whence)


class FileObjectPosix(object):
    """
    A file-like object that operates on non-blocking files but
    provides a synchronous, cooperative interface.

    .. note::
         Random read/write (e.g., ``mode='rwb'``) is not supported.
         For that, use :class:`io.BufferedRWPair` around two instance of this
         class.

    .. tip::
         Although this object provides a :meth:`fileno` method and
         so can itself be passed to :func:`fcntl.fcntl`, setting the
         :data:`os.O_NONBLOCK` flag will have no effect; likewise, removing
         that flag will cause this object to no longer be cooperative.
    """

    #: platform specific default for the *bufsize* parameter
    default_bufsize = io.DEFAULT_BUFFER_SIZE

    def __init__(self, fobj, mode='rb', bufsize=-1, close=True):
        """
        :keyword fobj: Either an integer fileno, or an object supporting the
            usual :meth:`socket.fileno` method. The file *will* be
            put in non-blocking mode using :func:`gevent.os.make_nonblocking`.
        :keyword str mode: The manner of access to the file, one of "rb", "rU" or "wb"
            (where the "b" or "U" can be omitted).
            If "U" is part of the mode, IO will be done on text, otherwise bytes.
        :keyword int bufsize: If given, the size of the buffer to use. The default
            value means to use a platform-specific default, and a value of 0 is translated
            to a value of 1. Other values are interpreted as for the :mod:`io` package.
            Buffering is ignored in text mode.
        """
        if isinstance(fobj, int):
            fileno = fobj
            fobj = None
        else:
            fileno = fobj.fileno()
        if not isinstance(fileno, int):
            raise TypeError('fileno must be int: %r' % fileno)

        orig_mode = mode
        mode = (mode or 'rb').replace('b', '')
        if 'U' in mode:
            self._translate = True
            mode = mode.replace('U', '')
        else:
            self._translate = False

        if len(mode) != 1 and mode not in 'rw': # pragma: no cover
            # Python 3 builtin `open` raises a ValueError for invalid modes;
            # Python 2 ignores it. In the past, we raised an AssertionError, if __debug__ was
            # enabled (which it usually was). Match Python 3 because it makes more sense
            # and because __debug__ may not be enabled.
            # NOTE: This is preventing a mode like 'rwb' for binary random access;
            # that code was never tested and was explicitly marked as "not used"
            raise ValueError('mode can only be [rb, rU, wb], not %r' % (orig_mode,))

        self._fobj = fobj
        self._closed = False
        self._close = close

        self.fileio = GreenFileDescriptorIO(fileno, mode, closefd=close)

        if bufsize < 0 or bufsize == 1:
            bufsize = self.default_bufsize
        elif bufsize == 0:
            bufsize = 1

        if mode == 'r':
            self.io = BufferedReader(self.fileio, bufsize)
        else:
            assert mode == 'w'
            self.io = BufferedWriter(self.fileio, bufsize)
        #else: # QQQ: not used, not reachable
        #
        #    self.io = BufferedRandom(self.fileio, bufsize)

        if self._translate:
            self.io = TextIOWrapper(self.io)

    @property
    def closed(self):
        """True if the file is cloed"""
        return self._closed

    def close(self):
        if self._closed:
            # make sure close() is only run once when called concurrently
            return
        self._closed = True
        try:
            self.io.close()
            self.fileio.close()
        finally:
            self._fobj = None

    def flush(self):
        self.io.flush()

    def fileno(self):
        return self.io.fileno()

    def write(self, data):
        self.io.write(data)

    def writelines(self, lines):
        self.io.writelines(lines)

    def read(self, size=-1):
        return self.io.read(size)

    def readline(self, size=-1):
        return self.io.readline(size)

    def readlines(self, sizehint=0):
        return self.io.readlines(sizehint)

    def readable(self):
        return self.io.readable()

    def writable(self):
        return self.io.writable()

    def seek(self, *args, **kwargs):
        return self.io.seek(*args, **kwargs)

    def seekable(self):
        return self.io.seekable()

    def tell(self):
        return self.io.tell()

    def truncate(self, size=None):
        return self.io.truncate(size)

    def __iter__(self):
        return self.io

    def __getattr__(self, name):
        # XXX: Should this really be _fobj, or self.io?
        # _fobj can easily be None but io never is
        return getattr(self._fobj, name)
