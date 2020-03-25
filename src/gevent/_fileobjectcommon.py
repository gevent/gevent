"""
gevent internals.
"""
from __future__ import absolute_import, print_function, division

try:
    from errno import EBADF
except ImportError:
    EBADF = 9

import io
import functools
import sys
import os

from gevent.hub import _get_hub_noargs as get_hub
from gevent._compat import PY2
from gevent._compat import integer_types
from gevent._compat import reraise
from gevent._compat import fspath
from gevent.lock import Semaphore, DummySemaphore

class cancel_wait_ex(IOError):

    def __init__(self):
        IOError.__init__(
            self,
            EBADF, 'File descriptor was closed in another greenlet')

class FileObjectClosed(IOError):

    def __init__(self):
        IOError.__init__(
            self,
            EBADF, 'Bad file descriptor (FileObject was closed)')

class UniversalNewlineBytesWrapper(io.TextIOWrapper):
    """
    Uses TextWrapper to decode universal newlines, but returns the
    results as bytes.

    This is for Python 2 where the 'rU' mode did that.
    """
    mode = None
    def __init__(self, fobj, line_buffering):
        # latin-1 has the ability to round-trip arbitrary bytes.
        io.TextIOWrapper.__init__(self, fobj, encoding='latin-1',
                                  newline=None,
                                  line_buffering=line_buffering)

    def read(self, *args, **kwargs):
        result = io.TextIOWrapper.read(self, *args, **kwargs)
        return result.encode('latin-1')

    def readline(self, limit=-1):
        result = io.TextIOWrapper.readline(self, limit)
        return result.encode('latin-1')

    def __iter__(self):
        # readlines() is implemented in terms of __iter__
        # and TextIOWrapper.__iter__ checks that readline returns
        # a unicode object, which we don't, so we override
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    next = __next__

class FlushingBufferedWriter(io.BufferedWriter):

    def write(self, b):
        ret = io.BufferedWriter.write(self, b)
        self.flush()
        return ret

class OpenDescriptor(object): # pylint:disable=too-many-instance-attributes
    """
    Interprets the arguments to `open`. Internal use only.

    Originally based on code in the stdlib's _pyio.py (Python implementation of
    the :mod:`io` module), but modified for gevent:

    - Native strings are returned on Python 2 when neither
      'b' nor 't' are in the mode string and no encoding is specified.
    - Universal newlines work in that mode.
    - Allows unbuffered text IO.
    """

    @staticmethod
    def _collapse_arg(preferred_val, old_val, default):
        if preferred_val is not None and old_val is not None:
            raise TypeError
        if preferred_val is None and old_val is None:
            return default
        return preferred_val if preferred_val is not None else old_val

    def __init__(self, fobj, mode='r', bufsize=None, close=None,
                 encoding=None, errors=None, newline=None,
                 buffering=None, closefd=None):
        # Based on code in the stdlib's _pyio.py from 3.8.
        # pylint:disable=too-many-locals,too-many-branches,too-many-statements
        closefd = self._collapse_arg(closefd, close, True)
        del close
        buffering = self._collapse_arg(buffering, bufsize, -1)
        del bufsize

        if not hasattr(fobj, 'fileno'):
            if not isinstance(fobj, integer_types):
                # Not a fd. Support PathLike on Python 2 and Python <= 3.5.
                fobj = fspath(fobj)
            if not isinstance(fobj, (str, bytes) + integer_types): # pragma: no cover
                raise TypeError("invalid file: %r" % fobj)
            if isinstance(fobj, (str, bytes)):
                closefd = True

        if not isinstance(mode, str):
            raise TypeError("invalid mode: %r" % mode)
        if not isinstance(buffering, integer_types):
            raise TypeError("invalid buffering: %r" % buffering)
        if encoding is not None and not isinstance(encoding, str):
            raise TypeError("invalid encoding: %r" % encoding)
        if errors is not None and not isinstance(errors, str):
            raise TypeError("invalid errors: %r" % errors)

        modes = set(mode)
        if modes - set("axrwb+tU") or len(mode) > len(modes):
            raise ValueError("invalid mode: %r" % mode)

        creating = "x" in modes
        reading = "r" in modes
        writing = "w" in modes
        appending = "a" in modes
        updating = "+" in modes
        text = "t" in modes
        binary = "b" in modes
        universal = 'U' in modes

        can_write = creating or writing or appending or updating

        if universal:
            if can_write:
                raise ValueError("mode U cannot be combined with 'x', 'w', 'a', or '+'")
            # Just because the stdlib deprecates this, no need for us to do so as well.
            # Especially not while we still support Python 2.
            # import warnings
            # warnings.warn("'U' mode is deprecated",
            #               DeprecationWarning, 4)
            reading = True
        if text and binary:
            raise ValueError("can't have text and binary mode at once")
        if creating + reading + writing + appending > 1:
            raise ValueError("can't have read/write/append mode at once")
        if not (creating or reading or writing or appending):
            raise ValueError("must have exactly one of read/write/append mode")
        if binary and encoding is not None:
            raise ValueError("binary mode doesn't take an encoding argument")
        if binary and errors is not None:
            raise ValueError("binary mode doesn't take an errors argument")
        if binary and newline is not None:
            raise ValueError("binary mode doesn't take a newline argument")
        if binary and buffering == 1:
            import warnings
            warnings.warn("line buffering (buffering=1) isn't supported in binary "
                          "mode, the default buffer size will be used",
                          RuntimeWarning, 4)

        self.fobj = fobj
        self.fileio_mode = (
            (creating and "x" or "")
            + (reading and "r" or "")
            + (writing and "w" or "")
            + (appending and "a" or "")
            + (updating and "+" or "")
        )
        self.mode = self.fileio_mode + ('t' if text else '') + ('b' if binary else '')

        self.creating = creating
        self.reading = reading
        self.writing = writing
        self.appending = appending
        self.updating = updating
        self.text = text
        self.binary = binary
        self.can_write = can_write
        self.can_read = reading or updating
        self.native = (
            not self.text and not self.binary # Neither t nor b given.
            and not encoding and not errors # And no encoding or error handling either.
        )
        self.universal = universal

        self.buffering = buffering
        self.encoding = encoding
        self.errors = errors
        self.newline = newline
        self.closefd = closefd

    default_buffer_size = io.DEFAULT_BUFFER_SIZE

    def is_fd(self):
        return isinstance(self.fobj, integer_types)

    def open(self):
        return self.open_raw_and_wrapped()[1]

    def open_raw_and_wrapped(self):
        raw = self.open_raw()
        try:
            return raw, self.wrapped(raw)
        except:
            raw.close()
            raise

    def open_raw(self):
        if hasattr(self.fobj, 'fileno'):
            return self.fobj
        return io.FileIO(self.fobj, self.fileio_mode, self.closefd)

    def wrapped(self, raw):
        """
        Wraps the raw IO object (`RawIOBase` or `io.TextIOBase`) in
        buffers, text decoding, and newline handling.
        """
        # pylint:disable=too-many-branches
        result = raw
        buffering = self.buffering

        line_buffering = False
        if buffering == 1 or buffering < 0 and raw.isatty():
            buffering = -1
            line_buffering = True
        if buffering < 0:
            buffering = self.default_buffer_size
            try:
                bs = os.fstat(raw.fileno()).st_blksize
            except (OSError, AttributeError):
                pass
            else:
                if bs > 1:
                    buffering = bs
        if buffering < 0: # pragma: no cover
            raise ValueError("invalid buffering size")

        if not isinstance(raw, io.BufferedIOBase) and \
           (not hasattr(raw, 'buffer') or raw.buffer is None):
            # Need to wrap our own buffering around it. If it
            # is already buffered, don't do so.
            if buffering != 0:
                if self.updating:
                    Buffer = io.BufferedRandom
                elif self.creating or self.writing or self.appending:
                    Buffer = io.BufferedWriter
                elif self.reading:
                    Buffer = io.BufferedReader
                else: # prgama: no cover
                    raise ValueError("unknown mode: %r" % self.mode)

                try:
                    result = Buffer(raw, buffering)
                except AttributeError:
                    # Python 2 file() objects don't have the readable/writable
                    # attributes. But they handle their own buffering.
                    result = raw

        if self.binary:
            if isinstance(raw, io.TextIOBase):
                # Can't do it. The TextIO object will have its own buffer, and
                # trying to read from the raw stream or the buffer without going through
                # the TextIO object is likely to lead to problems with the codec.
                raise ValueError("Unable to perform binary IO on top of text IO stream")
            return result

        # Either native or text at this point.
        if PY2 and self.native:
            # Neither text mode nor binary mode specified.
            if self.universal:
                # universal was requested, e.g., 'rU'
                result = UniversalNewlineBytesWrapper(result, line_buffering)
        else:
            # Python 2 and text mode, or Python 3 and either text or native (both are the same)
            if not isinstance(raw, io.TextIOBase):
                # Avoid double-wrapping a TextIOBase in another TextIOWrapper.
                # That tends not to work. See https://github.com/gevent/gevent/issues/1542
                result = io.TextIOWrapper(result, self.encoding, self.errors, self.newline,
                                          line_buffering)

        if result is not raw:
            # Set the mode, if possible, but only if we created a new
            # object.
            try:
                result.mode = self.mode
            except (AttributeError, TypeError):
                # AttributeError: No such attribute
                # TypeError: Readonly attribute (py2)
                pass

        return result


class FileObjectBase(object):
    """
    Internal base class to ensure a level of consistency
    between :class:`~.FileObjectPosix`, :class:`~.FileObjectThread`
    and :class:`~.FileObjectBlock`.
    """

    # List of methods we delegate to the wrapping IO object, if they
    # implement them and we do not.
    _delegate_methods = (
        # General methods
        'flush',
        'fileno',
        'writable',
        'readable',
        'seek',
        'seekable',
        'tell',

        # Read
        'read',
        'readline',
        'readlines',
        'read1',

        # Write
        'write',
        'writelines',
        'truncate',
    )


    _io = None

    def __init__(self, fobj, closefd):
        self._io = fobj
        # We don't actually use this property ourself, but we save it (and
        # pass it along) for compatibility.
        self._close = closefd

        self._do_delegate_methods()


    io = property(lambda s: s._io,
                  # Historically we either hand-wrote all the delegation methods
                  # to use self.io, or we simply used __getattr__ to look them up at
                  # runtime. This meant people could change the io attribute on the fly
                  # and it would mostly work (subprocess.py used to do that). We don't recommend
                  # that, but we still support it.
                  lambda s, nv: setattr(s, '_io', nv) or s._do_delegate_methods())

    def _do_delegate_methods(self):
        for meth_name in self._delegate_methods:
            meth = getattr(self._io, meth_name, None)
            implemented_by_class = hasattr(type(self), meth_name)
            if meth and not implemented_by_class:
                setattr(self, meth_name, self._wrap_method(meth))
            elif hasattr(self, meth_name) and not implemented_by_class:
                delattr(self, meth_name)

    def _wrap_method(self, method):
        """
        Wrap a method we're copying into our dictionary from the underlying
        io object to do something special or different, if necessary.
        """
        return method

    @property
    def closed(self):
        """True if the file is closed"""
        return self._io is None

    def close(self):
        if self._io is None:
            return

        fobj = self._io
        self._io = None
        self._do_close(fobj, self._close)

    def _do_close(self, fobj, closefd):
        raise NotImplementedError()

    def __getattr__(self, name):
        if self._io is None:
            raise FileObjectClosed()
        return getattr(self._io, name)

    def __repr__(self):
        return '<%s at 0x%x %s_fobj=%r%s>' % (
            self.__class__.__name__,
            id(self),
            'closed' if self.closed else '',
            self.io,
            self._extra_repr()
        )

    def _extra_repr(self):
        return ''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    next = __next__

    def __bool__(self):
        return True

    __nonzero__ = __bool__


class FileObjectBlock(FileObjectBase):
    """
    FileObjectBlock()

    A simple synchronous wrapper around a file object.

    Adds no concurrency or gevent compatibility.
    """

    def __init__(self, fobj, *args, **kwargs):
        descriptor = OpenDescriptor(fobj, *args, **kwargs)
        FileObjectBase.__init__(self, descriptor.open(), descriptor.closefd)

    def _do_close(self, fobj, closefd):
        fobj.close()


class FileObjectThread(FileObjectBase):
    """
    FileObjectThread()

    A file-like object wrapping another file-like object, performing all blocking
    operations on that object in a background thread.

    .. caution::
        Attempting to change the threadpool or lock of an existing FileObjectThread
        has undefined consequences.

    .. versionchanged:: 1.1b1
       The file object is closed using the threadpool. Note that whether or
       not this action is synchronous or asynchronous is not documented.
    """


    def __init__(self, *args, **kwargs):
        """
        :keyword bool lock: If True (the default) then all operations will
           be performed one-by-one. Note that this does not guarantee that, if using
           this file object from multiple threads/greenlets, operations will be performed
           in any particular order, only that no two operations will be attempted at the
           same time. You can also pass your own :class:`gevent.lock.Semaphore` to synchronize
           file operations with an external resource.
        :keyword bool closefd: If True (the default) then when this object is closed,
           the underlying object is closed as well. If *fobj* is a path, then
           *closefd* must be True.
        """
        lock = kwargs.pop('lock', True)
        threadpool = kwargs.pop('threadpool', None)
        descriptor = OpenDescriptor(*args, **kwargs)

        self.threadpool = threadpool or get_hub().threadpool
        self.lock = lock
        if self.lock is True:
            self.lock = Semaphore()
        elif not self.lock:
            self.lock = DummySemaphore()
        if not hasattr(self.lock, '__enter__'):
            raise TypeError('Expected a Semaphore or boolean, got %r' % type(self.lock))

        self.__io_holder = [descriptor.open()] # signal for _wrap_method
        FileObjectBase.__init__(self, self.__io_holder[0], descriptor.closefd)

    def _do_close(self, fobj, closefd):
        self.__io_holder[0] = None # for _wrap_method
        try:
            with self.lock:
                self.threadpool.apply(fobj.flush)
        finally:
            if closefd:
                # Note that we're not taking the lock; older code
                # did fobj.close() without going through the threadpool at all,
                # so acquiring the lock could potentially introduce deadlocks
                # that weren't present before. Avoiding the lock doesn't make
                # the existing race condition any worse.
                # We wrap the close in an exception handler and re-raise directly
                # to avoid the (common, expected) IOError from being logged by the pool
                def close(_fobj=fobj):
                    try:
                        _fobj.close()
                    except: # pylint:disable=bare-except
                        return sys.exc_info()
                    finally:
                        _fobj = None
                del fobj

                exc_info = self.threadpool.apply(close)
                del close

                if exc_info:
                    reraise(*exc_info)

    def _do_delegate_methods(self):
        FileObjectBase._do_delegate_methods(self)
        # if not hasattr(self, 'read1') and 'r' in getattr(self._io, 'mode', ''):
        #     self.read1 = self.read
        self.__io_holder[0] = self._io

    def _extra_repr(self):
        return ' threadpool=%r' % (self.threadpool,)

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if line:
            return line
        raise StopIteration
    __next__ = next

    def _wrap_method(self, method):
        # NOTE: We are careful to avoid introducing a refcycle
        # within self. Our wrapper cannot refer to self.
        io_holder = self.__io_holder
        lock = self.lock
        threadpool = self.threadpool

        @functools.wraps(method)
        def thread_method(*args, **kwargs):
            if io_holder[0] is None:
                # This is different than FileObjectPosix, etc,
                # because we want to save the expensive trip through
                # the threadpool.
                raise FileObjectClosed()
            with lock:
                return threadpool.apply(method, args, kwargs)

        return thread_method
