# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.
"""
Python 2 socket module.
"""
from __future__ import absolute_import

# Our import magic sadly makes this warning useless
# pylint: disable=undefined-variable

from gevent import _socketcommon
from gevent._util import copy_globals
from gevent._compat import PYPY
from gevent.timeout import Timeout

copy_globals(_socketcommon, globals(),
             names_to_ignore=_socketcommon.__py3_imports__ + _socketcommon.__extensions__,
             dunder_names_to_keep=())

__socket__ = _socketcommon.__socket__
__implements__ = _socketcommon._implements
__extensions__ = _socketcommon.__extensions__
__imports__ = [i for i in _socketcommon.__imports__ if i not in _socketcommon.__py3_imports__]
__dns__ = _socketcommon.__dns__
try:
    _fileobject = __socket__._fileobject
    _socketmethods = __socket__._socketmethods
except AttributeError:
    # Allow this module to be imported under Python 3
    # for building the docs
    _fileobject = object
    _socketmethods = ('bind', 'connect', 'connect_ex',
                      'fileno', 'listen', 'getpeername',
                      'getsockname', 'getsockopt',
                      'setsockopt', 'sendall',
                      'setblocking', 'settimeout',
                      'gettimeout', 'shutdown')
else:
    # Python 2 doesn't natively support with statements on _fileobject;
    # but it eases our test cases if we can do the same with on both Py3
    # and Py2. Implementation copied from Python 3
    assert not hasattr(_fileobject, '__enter__')
    # we could either patch in place:
    #_fileobject.__enter__ = lambda self: self
    #_fileobject.__exit__ = lambda self, *args: self.close() if not self.closed else None
    # or we could subclass. subclassing has the benefit of not
    # changing the behaviour of the stdlib if we're just imported; OTOH,
    # under Python 2.6/2.7, test_urllib2net.py asserts that the class IS
    # socket._fileobject (sigh), so we have to work around that.

    # We also make it call our custom socket closing method that disposes
    # if IO watchers but not the actual socket itself.

    # Python 2 relies on reference counting to close sockets, so this is all
    # very ugly and fragile.

    class _fileobject(_fileobject): # pylint:disable=function-redefined

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if not self.closed:
                self.close()

        def close(self):
            if self._sock is not None:
                self._sock._drop_events()
            super(_fileobject, self).close()


def _get_memory(data):
    try:
        mv = memoryview(data)
        if mv.shape:
            return mv
        # No shape, probably working with a ctypes object,
        # or something else exotic that supports the buffer interface
        return mv.tobytes()
    except TypeError:
        # fixes "python2.7 array.array doesn't support memoryview used in
        # gevent.socket.send" issue
        # (http://code.google.com/p/gevent/issues/detail?id=94)
        return buffer(data)


class _closedsocket(object):
    __slots__ = []

    def _dummy(*args, **kwargs): # pylint:disable=no-method-argument,unused-argument
        raise error(EBADF, 'Bad file descriptor')
    # All _delegate_methods must also be initialized here.
    send = recv = recv_into = sendto = recvfrom = recvfrom_into = _dummy

    if PYPY:

        def _drop(self):
            pass

        def _reuse(self):
            pass

    __getattr__ = _dummy


timeout_default = object()

from gevent._hub_primitives import wait_on_socket as _wait_on_socket

class socket(object):
    """
    gevent `socket.socket <https://docs.python.org/2/library/socket.html#socket-objects>`_
    for Python 2.

    This object should have the same API as the standard library socket linked to above. Not all
    methods are specifically documented here; when they are they may point out a difference
    to be aware of or may document a method the standard library does not.
    """

    # pylint:disable=too-many-public-methods

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        if _sock is None:
            self._sock = _realsocket(family, type, proto)
            self.timeout = _socket.getdefaulttimeout()
        else:
            if hasattr(_sock, '_sock'):
                # passed a gevent socket
                self._sock = _sock._sock
                self.timeout = getattr(_sock, 'timeout', False)
                if self.timeout is False:
                    self.timeout = _socket.getdefaulttimeout()
            else:
                # passed a native socket
                self._sock = _sock
                self.timeout = _socket.getdefaulttimeout()
            if PYPY:
                self._sock._reuse()
        self._sock.setblocking(0)
        fileno = self._sock.fileno()
        self.hub = get_hub()
        io = self.hub.loop.io
        self._read_event = io(fileno, 1)
        self._write_event = io(fileno, 2)

    def __repr__(self):
        return '<%s at %s %s>' % (type(self).__name__, hex(id(self)), self._formatinfo())

    def __str__(self):
        return '<%s %s>' % (type(self).__name__, self._formatinfo())

    def _formatinfo(self):
        # pylint:disable=broad-except
        try:
            fileno = self.fileno()
        except Exception as ex:
            fileno = str(ex)
        try:
            sockname = self.getsockname()
            sockname = '%s:%s' % sockname
        except Exception:
            sockname = None
        try:
            peername = self.getpeername()
            peername = '%s:%s' % peername
        except Exception:
            peername = None
        result = 'fileno=%s' % fileno
        if sockname is not None:
            result += ' sock=' + str(sockname)
        if peername is not None:
            result += ' peer=' + str(peername)
        if getattr(self, 'timeout', None) is not None:
            result += ' timeout=' + str(self.timeout)
        return result

    def _get_ref(self):
        return self._read_event.ref or self._write_event.ref

    def _set_ref(self, value):
        self._read_event.ref = value
        self._write_event.ref = value

    ref = property(_get_ref, _set_ref)

    _wait = _wait_on_socket

    def accept(self):
        sock = self._sock
        while True:
            try:
                client_socket, address = sock.accept()
                break
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)
        sockobj = socket(_sock=client_socket)
        if PYPY:
            client_socket._drop()
        return sockobj, address

    def _drop_events(self, cancel_wait_ex=cancel_wait_ex):
        if self._read_event is not None:
            self.hub.cancel_wait(self._read_event, cancel_wait_ex, True)
            self._read_event = None
        if self._write_event is not None:
            self.hub.cancel_wait(self._write_event, cancel_wait_ex, True)
            self._write_event = None


    def close(self, _closedsocket=_closedsocket):
        # This function should not reference any globals. See Python issue #808164.

        # Also break any reference to the loop.io objects. Our fileno, which they were
        # tied to, is now free to be reused, so these objects are no longer functional.
        self._drop_events()
        s = self._sock
        self._sock = _closedsocket()
        if PYPY:
            s._drop()

    @property
    def closed(self):
        return isinstance(self._sock, _closedsocket)

    def connect(self, address):
        if self.timeout == 0.0:
            return self._sock.connect(address)
        sock = self._sock
        if isinstance(address, tuple):
            r = getaddrinfo(address[0], address[1], sock.family)
            address = r[0][-1]

        timer = Timeout._start_new_or_dummy(self.timeout, timeout('timed out'))
        try:
            while True:
                err = sock.getsockopt(SOL_SOCKET, SO_ERROR)
                if err:
                    raise error(err, strerror(err))
                result = sock.connect_ex(address)
                if not result or result == EISCONN:
                    break
                elif (result in (EWOULDBLOCK, EINPROGRESS, EALREADY)) or (result == EINVAL and is_windows):
                    self._wait(self._write_event)
                else:
                    raise error(result, strerror(result))
        finally:
            timer.close()

    def connect_ex(self, address):
        try:
            return self.connect(address) or 0
        except timeout:
            return EAGAIN
        except error as ex:
            if type(ex) is error: # pylint:disable=unidiomatic-typecheck
                return ex.args[0]
            raise  # gaierror is not silenced by connect_ex

    def dup(self):
        """dup() -> socket object

        Return a new socket object connected to the same system resource.
        Note, that the new socket does not inherit the timeout."""
        return socket(_sock=self._sock)

    def makefile(self, mode='r', bufsize=-1):
        # Two things to look out for:
        # 1) Closing the original socket object should not close the
        #    fileobject (hence creating a new socket instance);
        #    An alternate approach is what _socket3.py does, which is to
        #    keep count of the times makefile objects have been opened (Py3's
        #    SocketIO helps with that). But the newly created socket, which
        #    has its own read/write watchers, does need those to be closed
        #    when the fileobject is; our custom subclass does that. Note that
        #    we can't pass the 'close=True' argument, as that causes reference counts
        #    to get screwed up, and Python2 sockets rely on those.
        # 2) The resulting fileobject must keep the timeout in order
        #    to be compatible with the stdlib's socket.makefile.
        # Pass self as _sock to preserve timeout.
        fobj = _fileobject(type(self)(_sock=self), mode, bufsize)
        if PYPY:
            self._sock._drop()
        return fobj

    def recv(self, *args):
        sock = self._sock  # keeping the reference so that fd is not closed during waiting
        while True:
            try:
                return sock.recv(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                # QQQ without clearing exc_info test__refcount.test_clean_exit fails
                sys.exc_clear()
            self._wait(self._read_event)

    def recvfrom(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recvfrom(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def recvfrom_into(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recvfrom_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def recv_into(self, *args):
        sock = self._sock
        while True:
            try:
                return sock.recv_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def send(self, data, flags=0, timeout=timeout_default):
        sock = self._sock
        if timeout is timeout_default:
            timeout = self.timeout
        try:
            return sock.send(data, flags)
        except error as ex:
            if ex.args[0] not in _socketcommon.GSENDAGAIN or timeout == 0.0:
                raise
            sys.exc_clear()
            self._wait(self._write_event)
            try:
                return sock.send(data, flags)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def sendall(self, data, flags=0):
        if isinstance(data, unicode):
            data = data.encode()
        # this sendall is also reused by gevent.ssl.SSLSocket subclass,
        # so it should not call self._sock methods directly
        data_memory = _get_memory(data)
        return _socketcommon._sendall(self, data_memory, flags)

    def sendto(self, *args):
        sock = self._sock
        try:
            return sock.sendto(*args)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                raise
            sys.exc_clear()
            self._wait(self._write_event)
            try:
                return sock.sendto(*args)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def setblocking(self, flag):
        if flag:
            self.timeout = None
        else:
            self.timeout = 0.0

    def settimeout(self, howlong):
        if howlong is not None:
            try:
                f = howlong.__float__
            except AttributeError:
                raise TypeError('a float is required')
            howlong = f()
            if howlong < 0.0:
                raise ValueError('Timeout value out of range')
        self.__dict__['timeout'] = howlong # avoid recursion with any property on self.timeout

    def gettimeout(self):
        return self.__dict__['timeout'] # avoid recursion with any property on self.timeout

    def shutdown(self, how):
        if how == 0:  # SHUT_RD
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        elif how == 1:  # SHUT_WR
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        else:
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        self._sock.shutdown(how)

    family = property(lambda self: self._sock.family)
    type = property(lambda self: self._sock.type)
    proto = property(lambda self: self._sock.proto)

    def fileno(self):
        return self._sock.fileno()

    def getsockname(self):
        return self._sock.getsockname()

    def getpeername(self):
        return self._sock.getpeername()

    # delegate the functions that we haven't implemented to the real socket object

    _s = "def %s(self, *args): return self._sock.%s(*args)\n\n"
    _m = None
    for _m in set(_socketmethods) - set(locals()):
        exec(_s % (_m, _m,))
    del _m, _s

    if PYPY:

        def _reuse(self):
            self._sock._reuse()

        def _drop(self):
            self._sock._drop()


SocketType = socket

if hasattr(_socket, 'socketpair'):

    def socketpair(family=getattr(_socket, 'AF_UNIX', _socket.AF_INET),
                   type=_socket.SOCK_STREAM, proto=0):
        one, two = _socket.socketpair(family, type, proto)
        result = socket(_sock=one), socket(_sock=two)
        if PYPY:
            one._drop()
            two._drop()
        return result
elif 'socketpair' in __implements__:
    __implements__.remove('socketpair')

if hasattr(_socket, 'fromfd'):

    def fromfd(fd, family, type, proto=0):
        s = _socket.fromfd(fd, family, type, proto)
        result = socket(_sock=s)
        if PYPY:
            s._drop()
        return result

elif 'fromfd' in __implements__:
    __implements__.remove('fromfd')

if hasattr(__socket__, 'ssl'):

    def ssl(sock, keyfile=None, certfile=None):
        # deprecated in 2.7.9 but still present;
        # sometimes backported by distros. See ssl.py
        # Note that we import gevent.ssl, not _ssl2, to get the correct
        # version.
        from gevent import ssl as _sslmod
        # wrap_socket is 2.7.9/backport, sslwrap_simple is older. They take
        # the same arguments.
        wrap = getattr(_sslmod, 'wrap_socket', None) or getattr(_sslmod, 'sslwrap_simple')
        return wrap(sock, keyfile, certfile)
    __implements__.append('ssl')

__all__ = __implements__ + __extensions__ + __imports__
