import sys
import os
from gevent.hub import get_hub
from gevent.lock import RLock
from gevent.socket import EBADF


try:
    from fcntl import fcntl, F_SETFL
except ImportError:
    fcntl = None


__all__ = ['FileObjectPosix',
           'FileObjectThreadPool',
           'FileObject']


if fcntl is None:

    __all__.remove('FileObjectPosix')

else:

    from gevent.socket import _fileobject, EAGAIN
    cancel_wait_ex = IOError(EBADF, 'File descriptor was closed in another greenlet')


    class SocketAdapter(object):
        """Socket-like API on top of a file descriptor.

        The main purpose of it is to re-use _fileobject to create proper cooperative file objects
        from file descriptors on POSIX platforms.
        """

        def __init__(self, fileno, mode=None):
            if not isinstance(fileno, (int, long)):
                raise TypeError('fileno must be int: %r' % fileno)
            self._fileno = fileno
            self._mode = mode or 'rb'
            self._translate = 'U' in mode
            fcntl(fileno, F_SETFL, os.O_NONBLOCK)
            self._eat_newline = False
            self.hub = get_hub()
            io = self.hub.loop.io
            self._read_event = io(fileno, 1)
            self._write_event = io(fileno, 2)

        def __repr__(self):
            if self._fileno is None:
                return '<%s closed>' % (self.__class__.__name__, )
            else:
                return '%s(%r, %r)' % (self.__class__.__name__, self._fileno, self._mode)

        def makefile(self, *args, **kwargs):
            return _fileobject(self, *args, **kwargs)

        def fileno(self):
            result = self._fileno
            if result is None:
                raise IOError(EBADF, 'Bad file descriptor (%s object is closed)' % self.__class__.__name)
            return result

        def close(self):
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
            fileno = self._fileno
            if fileno is not None:
                self._fileno = None
                os.close(fileno)

        def sendall(self, data):
            fileno = self.fileno()
            bytes_total = len(data)
            bytes_written = 0
            while bytes_written < bytes_total:
                try:
                    bytes_written += os.write(fileno, _get_memory(data, bytes_written))
                except (IOError, OSError):
                    code = sys.exc_info()[1].args[0]
                    if code == EINTR:
                        sys.exc_clear()
                        continue
                    elif code != EAGAIN:
                        raise
                    sys.exc_clear()
                self.hub.wait(self._write_event)

        def send(self, data):
            try:
                return os.write(self.fileno(), data)
            except (IOError, OSError):
                ex = sys.exc_info()[1]
                if ex.args[0] == EBADF:
                    return 0
                if ex.args[0] != EAGAIN:
                    raise
                sys.exc_clear()
                try:
                    self.hub.wait(self._write_event)
                except IOError:
                    ex = sys.exc_info()[1]
                    if ex.args[0] == EBADF:
                        return 0
                    raise
                try:
                    return os.write(self.fileno(), data)
                except (IOError, OSError):
                    ex2 = sys.exc_info()[1]
                    if ex2.args[0] in (EBADF, EAGAIN):
                        return 0
                    raise

        def recv(self, size):
            while True:
                try:
                    data = os.read(self.fileno(), size)
                except (IOError, OSError):
                    ex = sys.exc_info()[1]
                    if ex.args[0] == EBADF:
                        return ''
                    if ex.args[0] != EAGAIN:
                        raise
                    sys.exc_clear()
                else:
                    if not self._translate or not data:
                        return data
                    if self._eat_newline:
                        if data.startswith('\n'):
                            self._eat_newline = False
                            data = data[1:]
                            if not data:
                                return self.recv(size)
                    if data.endswith('\r'):
                        self._eat_newline = True
                    return self._translate_newlines(data)
                try:
                    self.hub.wait(self._read_event)
                except IOError:
                    ex = sys.exc_info()[1]
                    if ex.args[0] == EBADF:
                        return ''
                    raise

        def _translate_newlines(self, data):
            data = data.replace("\r\n", "\n")
            data = data.replace("\r", "\n")
            return data


    class FileObjectPosix(_fileobject):

        def __init__(self, fobj, mode='rb', bufsize=-1, close=True):
            if isinstance(fobj, (int, long)):
                fileno = fobj
                fobj = None
            else:
                fileno = fobj.fileno()
            sock = SocketAdapter(fileno, mode)
            self._fobj = fobj
            self._flushlock = RLock()
            _fileobject.__init__(self, sock, mode=mode, bufsize=bufsize, close=close)

        def __repr__(self):
            if self._sock is None:
                return '<%s closed>' % self.__class__.__name__
            elif self._fobj is None:
                return '<%s %s>' % (self.__class__.__name__, self._sock)
            else:
                return '<%s %s _fobj=%r>' % (self.__class__.__name__, self._sock, self._fobj)

        def close(self):
            sock = self._sock
            if sock is None:
                return
            try:
                self.flush()
            finally:
                self._sock = None
                if self._close:
                    sock.close()
                self._fobj = None
                # what if fobj has its own close() in __del__ like fdopen?

        def flush(self):
            # the reason we make flush() greenlet-safe is to make close() greenlet-safe
            with self._flushlock:
                return _fileobject.flush(self)

        def __getattr__(self, item):
            assert item != '_fobj'
            return getattr(self._fobj, item)


class FileObjectThreadPool(object):

    def __init__(self, fobj, mode='rb', bufsize=-1, close=True, threadpool=None):
        if isinstance(fobj, (int, long)):
            fobj = os.fdopen(fobj, mode, bufsize)
        self._fobj = fobj
        self._close = close
        if threadpool is None:
            threadpool = get_hub().threadpool
        self.threadpool = threadpool
        self._flushlock = RLock()

    def close(self):
        fobj = self._fobj
        if fobj is closedfileobject:
            return
        try:
            self.flush()
        finally:
            self._fobj = closedfileobject
            if self._close:
                fobj.close()

    def flush(self):
        # the reason we make flush() greenlet-safe is to make close() greenlet-safe
        fobj = self._fobj
        if fobj is closedfileobject:
            raise closedfileobject
        with self._flushlock:
            return self.threadpool.apply_e(BaseException, self._fobj.flush)

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    def __repr__(self):
        return '<%s _fobj=%r threadpool=%r>' % (self.__class__.__name__, self._fobj, self.threadpool)

    def __getattr__(self, item):
        assert item != '_fobj'
        return getattr(self._fobj, item)

    for method in ['read', 'readinto', 'readline', 'readlines', 'write', 'writelines', 'xreadlines']:

        exec '''def %s(self, *args, **kwargs):
    fobj = self._fobj
    if fobj is closedfileobject:
        raise closedfileobject
    return self.threadpool.apply_e(BaseException, fobj.%s, args, kwargs)''' % (method, method)

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if line:
            return line
        raise StopIteration


class closedfileobject(IOError):
    
    def __init__(self):
        IOError.__init__(self, EBADF, 'Bad file descriptor (FileObjectThreadPool was closed)')

    def _dummy(self, *args, **kwargs):
        raise self

    __getattr__ = _dummy
    __call__ = _dummy

closedfileobject = closedfileobject()


try:
    FileObject = FileObjectPosix
except NameError:
    FileObject = FileObjectThreadPool


config = os.environ.get('GEVENT_FILE')
if config:
    klass = {'thread': 'gevent.fileobject.FileObjectThreadPool',
             'posix': 'gevent.fileobject.FileObjectPosix'}.get(config, config)
    if klass.startswith('gevent.fileobject.'):
        FileObject = globals()[klass.split('.', 2)[-1]]
    else:
        from gevent.hub import _import
        FileObject = _import(klass)
    del klass
