from __future__ import absolute_import
import os
import sys
import io
from io import BufferedReader
from io import BufferedWriter
from io import BytesIO
from io import DEFAULT_BUFFER_SIZE
from io import RawIOBase
from io import UnsupportedOperation

from gevent._compat import reraise
from gevent._fileobjectcommon import cancel_wait_ex
from gevent._fileobjectcommon import FileObjectBase
from gevent.hub import get_hub
from gevent.os import _read
from gevent.os import _write
from gevent.os import ignored_errors
from gevent.os import make_nonblocking


class GreenFileDescriptorIO(RawIOBase):

    # Note that RawIOBase has a __del__ method that calls
    # self.close(). (In C implementations like CPython, this is
    # the type's tp_dealloc slot; prior to Python 3, the object doesn't
    # appear to have a __del__ method, even though it functionally does)

    _read_event = None
    _write_event = None
    _closed = False
    _seekable = None

    def __init__(self, fileno, mode='r', closefd=True):
        RawIOBase.__init__(self) # Python 2: pylint:disable=no-member,non-parent-init-called

        self._closefd = closefd
        self._fileno = fileno
        make_nonblocking(fileno)
        readable = 'r' in mode
        writable = 'w' in mode

        self.hub = get_hub()
        io_watcher = self.hub.loop.io
        try:
            if readable:
                self._read_event = io_watcher(fileno, 1)

            if writable:
                self._write_event = io_watcher(fileno, 2)
        except:
            # If anything goes wrong, it's important to go ahead and
            # close these watchers *now*, especially under libuv, so
            # that they don't get eventually reclaimed by the garbage
            # collector at some random time, thanks to the C level
            # slot (even though we don't seem to have any actual references
            # at the Python level). Previously, if we didn't close now,
            # that random close in the future would cause issues if we had duplicated
            # the fileno (if a wrapping with statement had closed an open fileobject,
            # for example)

            # test__fileobject can show a failure if this doesn't happen
            # TRAVIS=true GEVENT_LOOP=libuv python -m gevent.tests.test__fileobject \
            #    TestFileObjectPosix.test_seek TestFileObjectThread.test_bufsize_0
            self.close()
            raise

    def readable(self):
        return self._read_event is not None

    def writable(self):
        return self._write_event is not None

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

    def __destroy_events(self):
        read_event = self._read_event
        write_event = self._write_event
        hub = self.hub
        self.hub = self._read_event = self._write_event = None

        if read_event is not None:
            hub.cancel_wait(read_event, cancel_wait_ex, True)
        if write_event is not None:
            hub.cancel_wait(write_event, cancel_wait_ex, True)

    def close(self):
        if self._closed:
            return
        self.flush()
        # TODO: Can we use 'read_event is not None and write_event is
        # not None' to mean _closed?
        self._closed = True
        self.__destroy_events()
        fileno = self._fileno
        if self._closefd:
            self._fileno = None
            os.close(fileno)

    # RawIOBase provides a 'read' method that will call readall() if
    # the `size` was missing or -1 and otherwise call readinto(). We
    # want to take advantage of this to avoid single byte reads when
    # possible. This is highlighted by a bug in BufferedIOReader that
    # calls read() in a loop when its readall() method is invoked;
    # this was fixed in Python 3.3, but we still need our workaround for 2.7. See
    # https://github.com/gevent/gevent/issues/675)
    def __read(self, n):
        if self._read_event is None:
            raise UnsupportedOperation('read')
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
            data = self.__read(DEFAULT_BUFFER_SIZE)
            if not data:
                break
            ret.write(data)
        return ret.getvalue()

    def readinto(self, b):
        data = self.__read(len(b))
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
        if self._write_event is None:
            raise UnsupportedOperation('write')
        while True:
            try:
                return _write(self._fileno, b)
            except (IOError, OSError) as ex:
                if ex.args[0] not in ignored_errors:
                    raise
            self.hub.wait(self._write_event)

    def seek(self, offset, whence=0):
        try:
            return os.lseek(self._fileno, offset, whence)
        except IOError: # pylint:disable=try-except-raise
            raise
        except OSError as ex: # pylint:disable=duplicate-except
            # Python 2.x
            # make sure on Python 2.x we raise an IOError
            # as documented for RawIOBase.
            # See https://github.com/gevent/gevent/issues/1323
            reraise(IOError, IOError(*ex.args), sys.exc_info()[2])


class FlushingBufferedWriter(BufferedWriter):

    def write(self, b):
        ret = BufferedWriter.write(self, b)
        self.flush()
        return ret


class FileObjectPosix(FileObjectBase):
    """
    A file-like object that operates on non-blocking files but
    provides a synchronous, cooperative interface.

    .. caution::
         This object is only effective wrapping files that can be used meaningfully
         with :func:`select.select` such as sockets and pipes.

         In general, on most platforms, operations on regular files
         (e.g., ``open('a_file.txt')``) are considered non-blocking
         already, even though they can take some time to complete as
         data is copied to the kernel and flushed to disk: this time
         is relatively bounded compared to sockets or pipes, though.
         A :func:`~os.read` or :func:`~os.write` call on such a file
         will still effectively block for some small period of time.
         Therefore, wrapping this class around a regular file is
         unlikely to make IO gevent-friendly: reading or writing large
         amounts of data could still block the event loop.

         If you'll be working with regular files and doing IO in large
         chunks, you may consider using
         :class:`~gevent.fileobject.FileObjectThread` or
         :func:`~gevent.os.tp_read` and :func:`~gevent.os.tp_write` to bypass this
         concern.

    .. note::
         Random read/write (e.g., ``mode='rwb'``) is not supported.
         For that, use :class:`io.BufferedRWPair` around two instance of this
         class.

    .. tip::
         Although this object provides a :meth:`fileno` method and so
         can itself be passed to :func:`fcntl.fcntl`, setting the
         :data:`os.O_NONBLOCK` flag will have no effect (reads will
         still block the greenlet, although other greenlets can run).
         However, removing that flag *will cause this object to no
         longer be cooperative* (other greenlets will no longer run).

         You can use the internal ``fileio`` attribute of this object
         (a :class:`io.RawIOBase`) to perform non-blocking byte reads.
         Note, however, that once you begin directly using this
         attribute, the results from using methods of *this* object
         are undefined, especially in text mode. (See :issue:`222`.)

    .. versionchanged:: 1.1
       Now uses the :mod:`io` package internally. Under Python 2, previously
       used the undocumented class :class:`socket._fileobject`. This provides
       better file-like semantics (and portability to Python 3).
    .. versionchanged:: 1.2a1
       Document the ``fileio`` attribute for non-blocking reads.
    """

    #: platform specific default for the *bufsize* parameter
    default_bufsize = io.DEFAULT_BUFFER_SIZE

    def __init__(self, fobj, mode='rb', bufsize=-1, close=True):
        """
        :param fobj: Either an integer fileno, or an object supporting the
            usual :meth:`socket.fileno` method. The file *will* be
            put in non-blocking mode using :func:`gevent.os.make_nonblocking`.
        :keyword str mode: The manner of access to the file, one of "rb", "rU" or "wb"
            (where the "b" or "U" can be omitted).
            If "U" is part of the mode, universal newlines will be used. On Python 2,
            if 't' is not in the mode, this will result in returning byte (native) strings;
            putting 't'  in the mode will return text strings. This may cause
            :exc:`UnicodeDecodeError` to be raised.
        :keyword int bufsize: If given, the size of the buffer to use. The default
            value means to use a platform-specific default
            Other values are interpreted as for the :mod:`io` package.
            Buffering is ignored in text mode.

        .. versionchanged:: 1.3a1

           On Python 2, enabling universal newlines no longer forces unicode
           IO.

        .. versionchanged:: 1.2a1

           A bufsize of 0 in write mode is no longer forced to be 1.
           Instead, the underlying buffer is flushed after every write
           operation to simulate a bufsize of 0. In gevent 1.0, a
           bufsize of 0 was flushed when a newline was written, while
           in gevent 1.1 it was flushed when more than one byte was
           written. Note that this may have performance impacts.
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
            if bytes is str and 't' not in mode:
                # We're going to be producing unicode objects, but
                # universal newlines doesn't do that in the stdlib,
                # so fix that to return str objects. The fix is two parts:
                # first, set an encoding on the stream that can round-trip
                # all bytes, and second, decode all bytes once they've been read.
                self._translate_encoding = 'latin-1'
                import functools

                def wrap_method(m):
                    if m.__name__.startswith("read"):
                        @functools.wraps(m)
                        def wrapped(*args, **kwargs):
                            result = m(*args, **kwargs)
                            assert isinstance(result, unicode) # pylint:disable=undefined-variable
                            return result.encode('latin-1')
                        return wrapped
                    return m
                self._wrap_method = wrap_method
            mode = mode.replace('U', '')
        else:
            self._translate = False

        mode = mode.replace('t', '')

        if len(mode) != 1 and mode not in 'rw': # pragma: no cover
            # Python 3 builtin `open` raises a ValueError for invalid modes;
            # Python 2 ignores it. In the past, we raised an AssertionError, if __debug__ was
            # enabled (which it usually was). Match Python 3 because it makes more sense
            # and because __debug__ may not be enabled.
            # NOTE: This is preventing a mode like 'rwb' for binary random access;
            # that code was never tested and was explicitly marked as "not used"
            raise ValueError('mode can only be [rb, rU, wb], not %r' % (orig_mode,))


        self._orig_bufsize = bufsize
        if bufsize < 0 or bufsize == 1:
            bufsize = self.default_bufsize
        elif bufsize == 0:
            bufsize = 1

        if mode == 'r':
            IOFamily = BufferedReader
        else:
            assert mode == 'w'
            IOFamily = BufferedWriter
            if self._orig_bufsize == 0:
                # We could also simply pass self.fileio as *io*, but this way
                # we at least consistently expose a BufferedWriter in our *io*
                # attribute.
                IOFamily = FlushingBufferedWriter


        self._fobj = fobj
        # This attribute is documented as available for non-blocking reads.
        self.fileio = GreenFileDescriptorIO(fileno, mode, closefd=close)

        buffered_fobj = IOFamily(self.fileio, bufsize)

        super(FileObjectPosix, self).__init__(buffered_fobj, close)

    def _do_close(self, fobj, closefd):
        try:
            fobj.close()
            # self.fileio already knows whether or not to close the
            # file descriptor
            self.fileio.close()
        finally:
            self._fobj = None
            self.fileio = None

    def __iter__(self):
        return self._io
