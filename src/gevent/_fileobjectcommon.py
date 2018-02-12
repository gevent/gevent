from __future__ import absolute_import, print_function, division

try:
    from errno import EBADF
except ImportError:
    EBADF = 9

import os
from io import TextIOWrapper
import functools
import sys


from gevent.hub import get_hub
from gevent._compat import integer_types
from gevent._compat import reraise
from gevent.lock import Semaphore, DummySemaphore

class cancel_wait_ex(IOError):

    def __init__(self):
        super(cancel_wait_ex, self).__init__(
            EBADF, 'File descriptor was closed in another greenlet')


class FileObjectClosed(IOError):

    def __init__(self):
        super(FileObjectClosed, self).__init__(
            EBADF, 'Bad file descriptor (FileObject was closed)')

class FileObjectBase(object):
    """
    Internal base class to ensure a level of consistency
    between FileObjectPosix and FileObjectThread
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


    # Whether we are translating universal newlines or not.
    _translate = False

    _translate_encoding = None
    _translate_errors = None

    def __init__(self, io, closefd):
        """
        :param io: An io.IOBase-like object.
        """
        self._io = io
        # We don't actually use this property ourself, but we save it (and
        # pass it along) for compatibility.
        self._close = closefd

        if self._translate:
            # This automatically handles delegation by assigning to
            # self.io
            self.translate_newlines(None, self._translate_encoding, self._translate_errors)
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
        wrapper = TextIOWrapper(self._io, *text_args, **text_kwargs)
        if mode:
            wrapper.mode = mode
        self.io = wrapper
        self._translate = True

    @property
    def closed(self):
        """True if the file is closed"""
        return self._io is None

    def close(self):
        if self._io is None:
            return

        io = self._io
        self._io = None
        self._do_close(io, self._close)

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

class FileObjectBlock(FileObjectBase):

    def __init__(self, fobj, *args, **kwargs):
        closefd = kwargs.pop('close', True)
        if kwargs:
            raise TypeError('Unexpected arguments: %r' % kwargs.keys())
        if isinstance(fobj, integer_types):
            if not closefd:
                # we cannot do this, since fdopen object will close the descriptor
                raise TypeError('FileObjectBlock does not support close=False on an fd.')
            fobj = os.fdopen(fobj, *args)
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

    """

    def __init__(self, fobj, mode=None, bufsize=-1, close=True, threadpool=None, lock=True):
        """
        :param fobj: The underlying file-like object to wrap, or an integer fileno
           that will be pass to :func:`os.fdopen` along with *mode* and *bufsize*.
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
        if isinstance(fobj, integer_types):
            if not closefd:
                # we cannot do this, since fdopen object will close the descriptor
                raise TypeError('FileObjectThread does not support close=False on an fd.')
            if mode is None:
                assert bufsize == -1, "If you use the default mode, you can't choose a bufsize"
                fobj = os.fdopen(fobj)
            else:
                fobj = os.fdopen(fobj, mode, bufsize)

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
                def close():
                    try:
                        fobj.close()
                    except: # pylint:disable=bare-except
                        return sys.exc_info()
                exc_info = self.threadpool.apply(close)
                if exc_info:
                    reraise(*exc_info)

    def _do_delegate_methods(self):
        super(FileObjectThread, self)._do_delegate_methods()
        if not hasattr(self, 'read1') and 'r' in getattr(self._io, 'mode', ''):
            self.read1 = self.read
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
