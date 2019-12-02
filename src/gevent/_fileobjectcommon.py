from __future__ import absolute_import, print_function, division

try:
    from errno import EBADF
except ImportError:
    EBADF = 9

import io
import functools
import sys


from gevent.hub import _get_hub_noargs as get_hub
from gevent._compat import PY2
from gevent._compat import integer_types
from gevent._compat import reraise
from gevent._compat import fspath
from gevent.lock import Semaphore, DummySemaphore

class cancel_wait_ex(IOError):

    def __init__(self):
        super(cancel_wait_ex, self).__init__(
            EBADF, 'File descriptor was closed in another greenlet')


class FileObjectClosed(IOError):

    def __init__(self):
        super(FileObjectClosed, self).__init__(
            EBADF, 'Bad file descriptor (FileObject was closed)')

class _UniversalNewlineBytesWrapper(io.TextIOWrapper):
    """
    Uses TextWrapper to decode universal newlines, but returns the
    results as bytes.

    This is for Python 2 where the 'rU' mode did that.
    """

    def __init__(self, fobj):
        io.TextIOWrapper.__init__(self, fobj, encoding='latin-1', newline=None)

    def read(self, *args, **kwargs):
        result = io.TextIOWrapper.read(self, *args, **kwargs)
        return result.encode('latin-1')

    def readline(self, *args, **kwargs):
        result = io.TextIOWrapper.readline(self, *args, **kwargs)
        return result.encode('latin-1')

    def readlines(self, *args, **kwargs):
        result = io.TextIOWrapper.readlines(self, *args, **kwargs)
        return [x.encode('latin-1') for x in result]


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


    # Whether we should apply a TextWrapper (the names are historical).
    # Subclasses should set these before calling our constructor.
    _translate = False
    _translate_mode = None
    _translate_encoding = None
    _translate_errors = None
    _translate_newline = None # None means universal

    def __init__(self, fobj, closefd):
        """
        :param fobj: An io.IOBase-like object.
        """
        self._io = fobj
        # We don't actually use this property ourself, but we save it (and
        # pass it along) for compatibility.
        self._close = closefd

        if self._translate:
            # This automatically handles delegation by assigning to
            # self.io
            self.translate_newlines(self._translate_mode,
                                    self._translate_encoding,
                                    self._translate_errors)
        else:
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

    def translate_newlines(self, mode, *text_args, **text_kwargs):
        if mode == 'byte_newlines':
            wrapper = _UniversalNewlineBytesWrapper(self._io)
            mode = None
        else:
            wrapper = io.TextIOWrapper(self._io, *text_args, **text_kwargs)
        if mode:
            wrapper.mode = mode # pylint:disable=attribute-defined-outside-init
        self.io = wrapper
        self._translate = True

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
        return '<%s _fobj=%r%s>' % (self.__class__.__name__, self.io, self._extra_repr())

    def _extra_repr(self):
        return ''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # Modes that work with native strings on Python 2
    _NATIVE_PY2_MODES = ('r', 'r+', 'w', 'w+', 'a', 'a+')

    if PY2:
        @classmethod
        def _use_FileIO(cls, mode, encoding, errors):
            return mode in cls._NATIVE_PY2_MODES \
                and encoding is None and errors is None
    else:
        @classmethod
        def _use_FileIO(cls, mode, encoding, errors): # pylint:disable=unused-argument
            return False

    @classmethod
    def _open_raw(cls, fobj, mode='r', buffering=-1,
                  encoding=None, errors=None, newline=None, closefd=True):
        """
        Uses :func:`io.open` on *fobj* and returns the IO object.

        This is a compatibility wrapper for Python 2 and Python 3. It
        supports PathLike objects for *fobj* on all versions.

        If the object is already an object with a ``fileno`` method,
        it is returned unchanged.

        On Python 2, if the mode only specifies read, write or append,
        and encoding and errors are not specified, then
        :obj:`io.FileIO` is used to get the IO object. This ensures we
        return native strings unless explicitly requested.

        .. versionchanged: 1.5
           Support closefd for Python 2 native string readers.
        """
        if hasattr(fobj, 'fileno'):
            return fobj

        if not isinstance(fobj, integer_types):
            # Not an integer. Support PathLike on Python 2 and Python <= 3.5.
            fobj = fspath(fobj)
            closefd = True

        if cls._use_FileIO(mode, encoding, errors):
            # Python 2, default open. Return native str type, not unicode, which
            # is what would happen with io.open('r'), but we don't want to open the file
            # in binary mode since that skips newline conversion.
            fobj = io.FileIO(fobj, mode, closefd=closefd)
            if '+' in mode:
                BufFactory = io.BufferedRandom
            elif mode[0] == 'r':
                BufFactory = io.BufferedReader
            else:
                BufFactory = io.BufferedWriter

            if buffering == -1:
                fobj = BufFactory(fobj)
            elif buffering != 0:
                fobj = BufFactory(fobj, buffering)
        else:
            # Python 3, or we have a mode that Python 2's os.fdopen/open can't handle
            # (x) or they explicitly asked for binary or text mode.

            fobj = io.open(fobj, mode, buffering, encoding, errors, newline, closefd)
        return fobj

class FileObjectBlock(FileObjectBase):

    def __init__(self, fobj, *args, **kwargs):
        closefd = kwargs['closefd'] = kwargs.pop('close', True)
        if 'bufsize' in kwargs: # compat with other constructors
            kwargs['buffering'] = kwargs.pop('bufsize')
        fobj = self._open_raw(fobj, *args, **kwargs)
        super(FileObjectBlock, self).__init__(fobj, closefd)

    def _do_close(self, fobj, closefd):
        fobj.close()


class FileObjectThread(FileObjectBase):
    """
    A file-like object wrapping another file-like object, performing all blocking
    operations on that object in a background thread.

    .. caution::
        Attempting to change the threadpool or lock of an existing FileObjectThread
        has undefined consequences.

    .. versionchanged:: 1.1b1
       The file object is closed using the threadpool. Note that whether or
       not this action is synchronous or asynchronous is not documented.

    .. versionchanged:: 1.5
       Accept str and ``PathLike`` objects for *fobj* on all versions of Python.
    .. versionchanged:: 1.5
       Add *encoding*, *errors* and *newline* arguments.
    """

    def __init__(self, fobj, mode='r', bufsize=-1, close=True, threadpool=None, lock=True,
                 encoding=None, errors=None, newline=None):
        """
        :param fobj: The underlying file-like object to wrap, or something
           acceptable to :func:`io.open` (along with *mode* and *bufsize*, which is translated
           to *buffering*).
        :keyword bool lock: If True (the default) then all operations will
           be performed one-by-one. Note that this does not guarantee that, if using
           this file object from multiple threads/greenlets, operations will be performed
           in any particular order, only that no two operations will be attempted at the
           same time. You can also pass your own :class:`gevent.lock.Semaphore` to synchronize
           file operations with an external resource.
        :keyword bool close: If True (the default) then when this object is closed,
           the underlying object is closed as well.
        """
        closefd = close
        self.threadpool = threadpool or get_hub().threadpool
        self.lock = lock
        if self.lock is True:
            self.lock = Semaphore()
        elif not self.lock:
            self.lock = DummySemaphore()
        if not hasattr(self.lock, '__enter__'):
            raise TypeError('Expected a Semaphore or boolean, got %r' % type(self.lock))
        universal_newline = 'U' in mode or newline is None
        mode = mode.replace('U', '')
        fobj = self._open_raw(fobj, mode, bufsize,
                              encoding=encoding, errors=errors, newline=newline,
                              closefd=close)
        if self._use_FileIO(mode, encoding, errors) and universal_newline:
            self._translate_mode = 'byte_newlines'
            self._translate = True

        self.__io_holder = [fobj] # signal for _wrap_method
        super(FileObjectThread, self).__init__(fobj, closefd)

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
        super(FileObjectThread, self)._do_delegate_methods()
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
