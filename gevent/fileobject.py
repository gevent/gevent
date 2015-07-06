from __future__ import absolute_import
import sys
import os
from gevent._fileobjectcommon import FileObjectClosed
from gevent.hub import get_hub
from gevent.hub import integer_types
from gevent.hub import PY3
from gevent.lock import Semaphore, DummySemaphore


PYPY = hasattr(sys, 'pypy_version_info')

if hasattr(sys, 'exc_clear'):
    def _exc_clear():
        sys.exc_clear()
else:
    def _exc_clear():
        return

try:
    from fcntl import fcntl
except ImportError:
    fcntl = None


__all__ = ['FileObjectPosix',
           'FileObjectThread',
           'FileObject']


if fcntl is None:

    __all__.remove('FileObjectPosix')

else:

    if PY3:
        from gevent._fileobject3 import FileObjectPosix
    else:
        from gevent._fileobject2 import FileObjectPosix


class FileObjectThread(object):

    def __init__(self, fobj, *args, **kwargs):
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
                fobj.close()

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

    for method in ['read', 'readinto', 'readline', 'readlines', 'write', 'writelines', 'xreadlines']:

        exec('''def %s(self, *args, **kwargs):
    fobj = self.io
    if fobj is None:
        raise FileObjectClosed
    return self._apply(fobj.%s, args, kwargs)
''' % (method, method))

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if line:
            return line
        raise StopIteration
    __next__ = next


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
