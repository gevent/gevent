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
"""
from __future__ import absolute_import
import sys
import os
from gevent._fileobjectcommon import FileObjectClosed
from gevent.hub import get_hub
from gevent.hub import integer_types
from gevent.hub import reraise
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


class FileObjectThread(object):
    """
    A file-like object wrapping another file-like object, performing all blocking
    operations on that object in a background thread.
    """

    def __init__(self, fobj, *args, **kwargs):
        """
        :param fobj: The underlying file-like object to wrap, or an integer fileno
           that will be pass to :func:`os.fdopen` along with everything in *args*.
        :keyword bool lock: If True (the default) then all operations will
           be performed one-by-one. Note that this does not guarantee that, if using
           this file object from multiple threads/greenlets, operations will be performed
           in any particular order, only that no two operations will be attempted at the
           same time. You can also pass your own :class:`gevent.lock.Semaphore` to synchronize
           file operations with an external resource.
        :keyword bool close: If True (the default) then when this object is closed,
           the underlying object is closed as well.
        """
        self._close = kwargs.pop('close', True)
        self.threadpool = kwargs.pop('threadpool', None)
        self.lock = kwargs.pop('lock', True)
        if kwargs:
            raise TypeError('Unexpected arguments: %r' % kwargs.keys())
        if self.lock is True:
            self.lock = Semaphore()
        elif not self.lock:
            self.lock = DummySemaphore()
        if not hasattr(self.lock, '__enter__'):
            raise TypeError('Expected a Semaphore or boolean, got %r' % type(self.lock))
        if isinstance(fobj, integer_types):
            if not self._close:
                # we cannot do this, since fdopen object will close the descriptor
                raise TypeError('FileObjectThread does not support close=False')
            fobj = os.fdopen(fobj, *args)
        self.io = fobj
        if self.threadpool is None:
            self.threadpool = get_hub().threadpool

    def _apply(self, func, args=None, kwargs=None):
        with self.lock:
            return self.threadpool.apply(func, args, kwargs)

    def close(self):
        fobj = self.io
        if fobj is None:
            return
        self.io = None
        try:
            self.flush(_fobj=fobj)
        finally:
            if self._close:
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
                    except:
                        return sys.exc_info()
                exc_info = self.threadpool.apply(close)
                if exc_info:
                    reraise(*exc_info)

    def flush(self, _fobj=None):
        if _fobj is not None:
            fobj = _fobj
        else:
            fobj = self.io
        if fobj is None:
            raise FileObjectClosed
        return self._apply(fobj.flush)

    def __repr__(self):
        return '<%s _fobj=%r threadpool=%r>' % (self.__class__.__name__, self.io, self.threadpool)

    def __getattr__(self, item):
        if self.io is None:
            if item == 'closed':
                return True
            raise FileObjectClosed
        return getattr(self.io, item)

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if line:
            return line
        raise StopIteration
    __next__ = next

    def _wraps(method):
        def x(self, *args, **kwargs):
            fobj = self.io
            if fobj is None:
                raise FileObjectClosed
            return self._apply(getattr(fobj, method), args, kwargs)
        x.__name__ = method
        return x

    for method in ('read', 'readinto', 'readline', 'readlines', 'write', 'writelines', 'xreadlines'):
        locals()[method] = _wraps(method)
    del method
    del _wraps


try:
    FileObject = FileObjectPosix
except NameError:
    FileObject = FileObjectThread


class FileObjectBlock(object):

    def __init__(self, fobj, *args, **kwargs):
        self._close = kwargs.pop('close', True)
        if kwargs:
            raise TypeError('Unexpected arguments: %r' % kwargs.keys())
        if isinstance(fobj, integer_types):
            if not self._close:
                # we cannot do this, since fdopen object will close the descriptor
                raise TypeError('FileObjectBlock does not support close=False')
            fobj = os.fdopen(fobj, *args)
        self.io = fobj

    def __repr__(self):
        return '<%s %r>' % (self.io, )

    def __getattr__(self, item):
        assert item != '_fobj'
        if self.io is None:
            raise FileObjectClosed
        return getattr(self.io, item)


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
