# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.

import time
from gevent import _socketcommon
from gevent.hub import PYPY

for key in _socketcommon.__dict__:
    if key.startswith('__'):
        continue
    globals()[key] = getattr(_socketcommon, key)

__socket__ = _socketcommon.__socket__
__implements__ = _socketcommon._implements
__extensions__ = _socketcommon.__extensions__
__imports__ = _socketcommon.__imports__
__dns__ = _socketcommon.__dns__
_fileobject = __socket__._fileobject


if sys.version_info[:2] < (2, 7):
    _get_memory = buffer
else:
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

    def _dummy(*args, **kwargs):
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


class socket(object):

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        if _sock is None:
            self._sock = _realsocket(family, type, proto)
            self.timeout = _socket.getdefaulttimeout()
        else:
            if hasattr(_sock, '_sock'):
                self._sock = _sock._sock
                self.timeout = getattr(_sock, 'timeout', False)
                if self.timeout is False:
                    self.timeout = _socket.getdefaulttimeout()
            else:
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

    def _wait(self, watcher, timeout_exc=timeout('timed out')):
        """Block the current greenlet until *watcher* has pending events.

        If *timeout* is non-negative, then *timeout_exc* is raised after *timeout* second has passed.
        By default *timeout_exc* is ``socket.timeout('timed out')``.

        If :func:`cancel_wait` is called, raise ``socket.error(EBADF, 'File descriptor was closed in another greenlet')``.
        """
        assert watcher.callback is None, 'This socket is already used by another greenlet: %r' % (watcher.callback, )
        if self.timeout is not None:
            timeout = Timeout.start_new(self.timeout, timeout_exc, ref=False)
        else:
            timeout = None
        try:
            self.hub.wait(watcher)
        finally:
            if timeout is not None:
                timeout.cancel()

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

    def close(self, _closedsocket=_closedsocket, cancel_wait_ex=cancel_wait_ex):
        # This function should not reference any globals. See Python issue #808164.
        self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        self.hub.cancel_wait(self._write_event, cancel_wait_ex)
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
            r = getaddrinfo(address[0], address[1], sock.family, sock.type, sock.proto)
            address = r[0][-1]
        if self.timeout is not None:
            timer = Timeout.start_new(self.timeout, timeout('timed out'))
        else:
            timer = None
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
            if timer is not None:
                timer.cancel()

    def connect_ex(self, address):
        try:
            return self.connect(address) or 0
        except timeout:
            return EAGAIN
        except error as ex:
            if type(ex) is error:
                return ex.args[0]
            else:
                raise  # gaierror is not silented by connect_ex

    def dup(self):
        """dup() -> socket object

        Return a new socket object connected to the same system resource.
        Note, that the new socket does not inherit the timeout."""
        return socket(_sock=self._sock)

    def makefile(self, mode='r', bufsize=-1):
        # Two things to look out for:
        # 1) Closing the original socket object should not close the
        #    socket (hence creating a new instance)
        # 2) The resulting fileobject must keep the timeout in order
        #    to be compatible with the stdlib's socket.makefile.
        fobj = _fileobject(type(self)(_sock=self._sock), mode, bufsize)
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
            if ex.args[0] != EWOULDBLOCK or timeout == 0.0:
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
        if self.timeout is None:
            data_sent = 0
            while data_sent < len(data_memory):
                data_sent += self.send(data_memory[data_sent:], flags)
        else:
            timeleft = self.timeout
            end = time.time() + timeleft
            data_sent = 0
            while True:
                data_sent += self.send(data_memory[data_sent:], flags, timeout=timeleft)
                if data_sent >= len(data_memory):
                    return
                timeleft = end - time.time()
                if timeleft <= 0:
                    raise timeout('timed out')

    def sendto(self, *args):
        sock = self._sock
        try:
            return sock.sendto(*args)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or timeout == 0.0:
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

    family = property(lambda self: self._sock.family, doc="the socket family")
    type = property(lambda self: self._sock.type, doc="the socket type")
    proto = property(lambda self: self._sock.proto, doc="the socket protocol")

    # delegate the functions that we haven't implemented to the real socket object

    _s = ("def %s(self, *args): return self._sock.%s(*args)\n\n"
          "%s.__doc__ = _realsocket.%s.__doc__\n")
    for _m in set(__socket__._socketmethods) - set(locals()):
        exec(_s % (_m, _m, _m, _m))
    del _m, _s

    if PYPY:

        def _reuse(self):
            self._sock._reuse()

        def _drop(self):
            self._sock._drop()


SocketType = socket

if hasattr(_socket, 'socketpair'):

    def socketpair(*args):
        one, two = _socket.socketpair(*args)
        result = socket(_sock=one), socket(_sock=two)
        if PYPY:
            one._drop()
            two._drop()
        return result
else:
    __implements__.remove('socketpair')

if hasattr(_socket, 'fromfd'):

    def fromfd(*args):
        s = _socket.fromfd(*args)
        result = socket(_sock=s)
        if PYPY:
            s._drop()
        return result

else:
    __implements__.remove('fromfd')

if hasattr(__socket__, 'ssl'):
    from gevent.hub import PYGTE279

    def ssl(sock, keyfile=None, certfile=None):
        # deprecated in 2.7.9 but still present
        if PYGTE279:
            from . import _sslgte279
            return _sslgte279.wrap_socket(sock, keyfile, certfile)
        else:
            from . import _ssl2
            return _ssl2.sslwrap_simple(sock, keyfile, certfile)
    __implements__.append('ssl')

__all__ = __implements__ + __extensions__ + __imports__
