import os
from io import BufferedRandom
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
        super().__init__()
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

    def readable(self):
        return self._readable

    def writable(self):
        return self._writable

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


class FileObjectPosix:
    default_bufsize = 8192

    def __init__(self, fobj, mode='rb', bufsize=-1, close=True):
        if isinstance(fobj, int):
            fileno = fobj
            fobj = None
        else:
            fileno = fobj.fileno()
        if not isinstance(fileno, int):
            raise TypeError('fileno must be int: %r' % fileno)

        mode = (mode or 'rb').replace('b', '')
        if 'U' in mode:
            self._translate = True
            mode = mode.replace('U', '')
        else:
            self._translate = False
        assert len(mode) == 1, 'mode can only be [rb, rU, wb]'

        self._fobj = fobj
        self._closed = False
        self._close = close

        self.fileio = GreenFileDescriptorIO(fileno, mode, closefd=close)

        if bufsize < 0:
            bufsize = self.default_bufsize
        if mode == 'r':
            if bufsize == 0:
                bufsize = 1
            elif bufsize == 1:
                bufsize = self.default_bufsize
            self.io = BufferedReader(self.fileio, bufsize)
        elif mode == 'w':
            self.io = BufferedWriter(self.fileio, bufsize)
        else:
            # QQQ: not used
            self.io = BufferedRandom(self.fileio, bufsize)
        if self._translate:
            self.io = TextIOWrapper(self.io)

    @property
    def closed(self):
        """True if the file is cloed"""
        return self._closed

    def close(self):
        if self._closed:
            # make sure close() is only ran once when called concurrently
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

    def writelines(self, list):
        self.io.writelines(list)

    def read(self, size=-1):
        return self.io.read(size)

    def readline(self, size=-1):
        return self.io.readline(size)

    def readlines(self, sizehint=0):
        return self.io.readlines(sizehint)

    def __iter__(self):
        return self.io
