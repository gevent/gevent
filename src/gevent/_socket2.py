# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.
"""
Python 2 socket module.
"""
from __future__ import absolute_import
from __future__ import print_function

# Our import magic sadly makes this warning useless
# pylint: disable=undefined-variable
import sys

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
    # but it substantially eases our test cases if we can do the same with on both Py3
    # and Py2. (For this same reason we make the socket itself a context manager.)
    # Implementation copied from Python 3
    assert not hasattr(_fileobject, '__enter__')
    # we could either patch in place:
    #_fileobject.__enter__ = lambda self: self
    #_fileobject.__exit__ = lambda self, *args: self.close() if not self.closed else None
    # or we could subclass. subclassing has the benefit of not
    # changing the behaviour of the stdlib if we're just imported; OTOH,
    # under Python 2.6/2.7, test_urllib2net.py asserts that the class IS
    # socket._fileobject (sigh), so we have to work around that.

    # We also make it call our custom socket closing method that disposes
    # of IO watchers but not the actual socket itself.

    # Python 2 relies on reference counting to close sockets, so this is all
    # very ugly and fragile.

    class _fileobject(_fileobject): # pylint:disable=function-redefined
        __slots__ = (
            '__weakref__',
        )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if not self.closed:
                self.close()

        def close(self):
            if self._sock is not None:
                self._sock._drop_events_and_close(closefd=False)
            super(_fileobject, self).close()


from gevent._greenlet_primitives import get_memory as _get_memory

class _closedsocket(object):
    __slots__ = ()

    def _dummy(*args, **kwargs): # pylint:disable=no-method-argument,unused-argument
        raise error(EBADF, 'Bad file descriptor')
    # All _delegate_methods must also be initialized here.
    send = recv = recv_into = sendto = recvfrom = recvfrom_into = _dummy

    def __nonzero__(self):
        return False

    __bool__ = __nonzero__

    if PYPY:

        def _drop(self):
            pass

        def _reuse(self):
            pass

    __getattr__ = _dummy


timeout_default = object()
gtype = type

from gevent._hub_primitives import wait_on_socket as _wait_on_socket

class socket(_socketcommon.SocketMixin):
    """
    gevent `socket.socket <https://docs.python.org/2/library/socket.html#socket-objects>`_
    for Python 2.

    This object should have the same API as the standard library socket linked to above. Not all
    methods are specifically documented here; when they are they may point out a difference
    to be aware of or may document a method the standard library does not.

    .. versionchanged:: 1.5.0
        This object is a context manager, returning itself, like in Python 3.
    """

    # pylint:disable=too-many-public-methods

    # TODO: Define __slots__.

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, _sock=None):
        timeout = _socket.getdefaulttimeout()
        if _sock is None:
            self._sock = _realsocket(family, type, proto)
        else:
            if hasattr(_sock, '_sock'):
                timeout = getattr(_sock, 'timeout', timeout)
                while hasattr(_sock, '_sock'):
                    # passed a gevent socket or a native
                    # socket._socketobject. Unwrap this all the way to the
                    # native _socket.socket.
                    _sock = _sock._sock

            self._sock = _sock

            if PYPY:
                self._sock._reuse()
        self.timeout = timeout
        self._sock.setblocking(0)
        fileno = self._sock.fileno()
        self.hub = get_hub()
        io = self.hub.loop.io
        self._read_event = io(fileno, 1)
        self._write_event = io(fileno, 2)

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        self.close()

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
        while 1:
            try:
                client_socket, address = self._sock.accept()
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


    def _drop_ref_on_close(self, sock):
        # See the same method in _socket3.py. We just can't be as deterministic
        # as we can on Python 3.
        scheduled_new = self.hub.loop.closing_fd(sock.fileno())
        if PYPY:
            meth = sock._drop
        else:
            meth = sock.fileno # Still keep it alive if we need to
        if scheduled_new:
            self.hub.loop.run_callback(meth)
        else:
            meth()

    def close(self, _closedsocket=_closedsocket):
        if not self._sock:
            return

        # This function should not reference any globals. See Python issue #808164.

        # First, break any reference to the loop.io objects. Our
        # fileno, which they were tied to, is about to be free to be
        # reused, so these objects are no longer functional.
        self._drop_events_and_close()

        # Next, change self._sock. On CPython, this drops a
        # reference, and if it was the last reference, __del__ will
        # close it. (We cannot close it, makefile() relies on
        # reference counting like this, and it may be shared among
        # multiple wrapper objects). Methods *must not* cache
        # `self._sock` separately from
        # self._write_event/self._read_event, or they will be out of
        # sync and we may get inappropriate errors. (See
        # test__hub:TestCloseSocketWhilePolling for an example).
        self._sock = _closedsocket()

    @property
    def closed(self):
        return isinstance(self._sock, _closedsocket)

    def connect(self, address):
        if self.timeout == 0.0:
            return self._sock.connect(address)

        address = _socketcommon._resolve_addr(self._sock, address)

        timer = Timeout._start_new_or_dummy(self.timeout, timeout('timed out'))
        try:
            while 1:
                err = self._sock.getsockopt(SOL_SOCKET, SO_ERROR)
                if err:
                    raise error(err, strerror(err))
                result = self._sock.connect_ex(address)
                if not result or result == EISCONN:
                    break
                if (result in (EWOULDBLOCK, EINPROGRESS, EALREADY)) or (result == EINVAL and is_windows):
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
        while 1:
            try:
                return self._sock.recv(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                # QQQ without clearing exc_info test__refcount.test_clean_exit fails
                sys.exc_clear()
            self._wait(self._read_event)

    def recvfrom(self, *args):
        while 1:
            try:
                return self._sock.recvfrom(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def recvfrom_into(self, *args):
        while 1:
            try:
                return self._sock.recvfrom_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def recv_into(self, *args):
        while 1:
            try:
                return self._sock.recv_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                sys.exc_clear()
            self._wait(self._read_event)

    def send(self, data, flags=0, timeout=timeout_default):
        if timeout is timeout_default:
            timeout = self.timeout
        try:
            return self._sock.send(data, flags)
        except error as ex:
            if ex.args[0] not in _socketcommon.GSENDAGAIN or timeout == 0.0:
                raise
            sys.exc_clear()
            self._wait(self._write_event)
            try:
                return self._sock.send(data, flags)
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
        try:
            return self._sock.sendto(*args)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                raise
            sys.exc_clear()
            self._wait(self._write_event)
            try:
                return self._sock.sendto(*args)
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
