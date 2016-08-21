"""
Wrappers to make file-like objects cooperative.

.. class:: FileObject

   The main entry point to the file-like gevent-compatible behaviour. It will be defined
   to be the best available implementation.

There are two main implementations of ``FileObject``. On all systems,
there is :class:`FileObjectThread` which uses the built-in native
threadpool to avoid blocking the entire interpreter. On UNIX systems
(those that support the :mod:`fcntl` module), there is also
:class:`FileObjectPosix` which uses native non-blocking semantics.

A third class, :class:`FileObjectBlock`, is simply a wrapper that executes everything
synchronously (and so is not gevent-compatible). It is provided for testing and debugging
purposes.

Configuration
=============

You may change the default value for ``FileObject`` using the
``GEVENT_FILE`` environment variable. Set it to ``posix``, ``thread``,
or ``block`` to choose from :class:`FileObjectPosix`,
:class:`FileObjectThread` and :class:`FileObjectBlock`, respectively.
You may also set it to the fully qualified class name of another
object that implements the file interface to use one of your own
objects.

.. note:: The environment variable must be set at the time this module
   is first imported.

Classes
=======
"""
from __future__ import absolute_import

import functools
import sys
import os

from gevent._fileobjectcommon import FileObjectClosed
from gevent._fileobjectcommon import FileObjectBase
from gevent.hub import get_hub
from gevent._compat import integer_types
from gevent._compat import reraise
from gevent.lock import Semaphore, DummySemaphore


PYPY = hasattr(sys, 'pypy_version_info')

if hasattr(sys, 'exc_clear'):
    def _exc_clear():
        sys.exc_clear()
else:
    def _exc_clear():
        return


__all__ = ['FileObjectPosix',
           'FileObjectThread',
           'FileObject']

try:
    from fcntl import fcntl
except ImportError:
    __all__.remove("FileObjectPosix")
else:
    del fcntl
    from gevent._fileobjectposix import FileObjectPosix


class FileObjectThread(FileObjectBase):
    """
    A file-like object wrapping another file-like object, performing all blocking
    operations on that object in a background thread.

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
        self.threadpool = threadpool
        self.lock = lock
        if self.lock is True:
            self.lock = Semaphore()
        elif not self.lock:
            self.lock = DummySemaphore() # pylint:disable=redefined-variable-type
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
        if self.threadpool is None:
            self.threadpool = get_hub().threadpool
        super(FileObjectThread, self).__init__(fobj, closefd)

    def _apply(self, func, args=None, kwargs=None):
        with self.lock:
            return self.threadpool.apply(func, args, kwargs)

    def _do_close(self, fobj, closefd):
        try:
            self._apply(fobj.flush)
        finally:
            if closefd:
                # Note that we're not using self._apply; older code
                # did fobj.close() without going through the threadpool at all,
                # so acquiring the lock could potentially introduce deadlocks
                # that weren't present before. Avoiding the lock doesn't make
                # the existing race condition any worse.
                # We wrap the close in an exception handler and re-raise directly
                # to avoid the (common, expected) IOError from being logged
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
        if not hasattr(self, 'read1') and 'r' in self._io.mode:
            self.read1 = self.read

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
        @functools.wraps(method)
        def thread_method(*args, **kwargs):
            if self._io is None:
                # This is different than FileObjectPosix, etc,
                # because we want to save the expensive trip through
                # the threadpool.
                raise FileObjectClosed()
            return self._apply(method, args, kwargs)
        return thread_method


try:
    FileObject = FileObjectPosix
except NameError:
    FileObject = FileObjectThread


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

config = os.environ.get('GEVENT_FILE')
if config:
    klass = {'thread': 'gevent.fileobject.FileObjectThread',
             'posix': 'gevent.fileobject.FileObjectPosix',
             'block': 'gevent.fileobject.FileObjectBlock'}.get(config, config)
    if klass.startswith('gevent.fileobject.'):
        FileObject = globals()[klass.split('.', 2)[-1]]
    else:
        from gevent.hub import _import
        FileObject = _import(klass)
    del klass
