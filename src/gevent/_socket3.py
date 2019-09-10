# Port of Python 3.3's socket module to gevent
"""
Python 3 socket module.
"""
# Our import magic sadly makes this warning useless
# pylint: disable=undefined-variable
# pylint: disable=too-many-statements,too-many-branches
# pylint: disable=too-many-public-methods,unused-argument
from __future__ import absolute_import
import io
import os
import sys

from gevent import _socketcommon
from gevent._util import copy_globals
from gevent._compat import PYPY
from gevent.timeout import Timeout
import _socket
from os import dup


copy_globals(_socketcommon, globals(),
             names_to_ignore=_socketcommon.__extensions__,
             dunder_names_to_keep=())

try:
    from errno import EHOSTUNREACH
    from errno import ECONNREFUSED
except ImportError:
    EHOSTUNREACH = -1
    ECONNREFUSED = -1


__socket__ = _socketcommon.__socket__
__implements__ = _socketcommon._implements
__extensions__ = _socketcommon.__extensions__
__imports__ = _socketcommon.__imports__
__dns__ = _socketcommon.__dns__


SocketIO = __socket__.SocketIO # pylint:disable=no-member

from gevent._greenlet_primitives import get_memory as _get_memory

timeout_default = object()

class _closedsocket(object):
    __slots__ = ('family', 'type', 'proto', 'orig_fileno', 'description')

    def __init__(self, family, type, proto, orig_fileno, description):
        self.family = family
        self.type = type
        self.proto = proto
        self.orig_fileno = orig_fileno
        self.description = description

    def fileno(self):
        return -1

    def close(self):
        "No-op"

    detach = fileno

    def _dummy(*args, **kwargs): # pylint:disable=no-method-argument,unused-argument
        raise OSError(EBADF, 'Bad file descriptor')
    # All _delegate_methods must also be initialized here.
    send = recv = recv_into = sendto = recvfrom = recvfrom_into = _dummy
    getsockname = _dummy

    def __bool__(self):
        return False

    __getattr__ = _dummy

    def __repr__(self):
        return "<socket object [closed proxy at 0x%x fd=%s %s]>" % (
            id(self),
            self.orig_fileno,
            self.description,
        )

class _wrefsocket(_socket.socket):
    # Plain stdlib socket.socket objects subclass _socket.socket
    # and add weakref ability. The ssl module, for one, counts on this.
    # We don't create socket.socket objects (because they may have been
    # monkey patched to be the object from this module), but we still
    # need to make sure what we do create can be weakrefd.

    __slots__ = ("__weakref__", )

    if PYPY:
        # server.py unwraps the socket object to get the raw _sock;
        # it depends on having a timeout property alias, which PyPy does not
        # provide.
        timeout = property(lambda s: s.gettimeout(),
                           lambda s, nv: s.settimeout(nv))

from gevent._hub_primitives import wait_on_socket as _wait_on_socket

class socket(object):
    """
    gevent `socket.socket <https://docs.python.org/3/library/socket.html#socket-objects>`_
    for Python 3.

    This object should have the same API as the standard library socket linked to above. Not all
    methods are specifically documented here; when they are they may point out a difference
    to be aware of or may document a method the standard library does not.
    """

    # Subclasses can set this to customize the type of the
    # native _socket.socket we create. It MUST be a subclass
    # of _wrefsocket. (gevent internal usage only)
    _gevent_sock_class = _wrefsocket

    _io_refs = 0
    _closed = False
    _read_event = None
    _write_event = None


    # Take the same approach as socket2: wrap a real socket object,
    # don't subclass it. This lets code that needs the raw _sock (not tied to the hub)
    # get it. This shows up in tests like test__example_udp_server.

    if sys.version_info[:2] < (3, 7):
        def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
            self._sock = self._gevent_sock_class(family, type, proto, fileno)
            self.timeout = None
            self.__init_common()
    else:
        # In 3.7, socket changed to auto-detecting family, type, and proto
        # when given a fileno.
        def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
            if fileno is None:
                if family == -1:
                    family = AF_INET
                if type == -1:
                    type = SOCK_STREAM
                if proto == -1:
                    proto = 0
            self._sock = self._gevent_sock_class(family, type, proto, fileno)
            self.timeout = None
            self.__init_common()

    def __init_common(self):
        _socket.socket.setblocking(self._sock, False)
        fileno = _socket.socket.fileno(self._sock)
        self.hub = get_hub()
        io_class = self.hub.loop.io
        self._read_event = io_class(fileno, 1)
        self._write_event = io_class(fileno, 2)
        self.timeout = _socket.getdefaulttimeout()

    def __getattr__(self, name):
        return getattr(self._sock, name)

    if hasattr(_socket, 'SOCK_NONBLOCK'):
        # Only defined under Linux
        @property
        def type(self):
            # See https://github.com/gevent/gevent/pull/399
            if self.timeout != 0.0:
                return self._sock.type & ~_socket.SOCK_NONBLOCK # pylint:disable=no-member
            return self._sock.type

    def getblocking(self):
        """
        Returns whether the socket will approximate blocking
        behaviour.

        .. versionadded:: 1.3a2
            Added in Python 3.7.
        """
        return self.timeout != 0.0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self._closed:
            self.close()

    def __repr__(self):
        """Wrap __repr__() to reveal the real class name."""
        try:
            s = repr(self._sock)
        except Exception as ex: # pylint:disable=broad-except
            # Observed on Windows Py3.3, printing the repr of a socket
            # that just suffered a ConnectionResetError [WinError 10054]:
            # "OverflowError: no printf formatter to display the socket descriptor in decimal"
            # Not sure what the actual cause is or if there's a better way to handle this
            s = '<socket [%r]>' % ex

        if s.startswith("<socket object"):
            s = "<%s.%s%s at 0x%x%s%s" % (
                self.__class__.__module__,
                self.__class__.__name__,
                getattr(self, '_closed', False) and " [closed]" or "",
                id(self),
                self._extra_repr(),
                s[7:])
        return s

    def _extra_repr(self):
        return ''

    def __getstate__(self):
        raise TypeError("Cannot serialize socket object")

    def _get_ref(self):
        return self._read_event.ref or self._write_event.ref

    def _set_ref(self, value):
        self._read_event.ref = value
        self._write_event.ref = value

    ref = property(_get_ref, _set_ref)

    _wait = _wait_on_socket

    def dup(self):
        """dup() -> socket object

        Return a new socket object connected to the same system resource.
        """
        fd = dup(self.fileno())
        sock = self.__class__(self.family, self.type, self.proto, fileno=fd)
        sock.settimeout(self.gettimeout())
        return sock

    def accept(self):
        """accept() -> (socket object, address info)

        Wait for an incoming connection.  Return a new socket
        representing the connection, and the address of the client.
        For IP sockets, the address info is a pair (hostaddr, port).
        """
        while True:
            try:
                fd, addr = self._accept()
                break
            except BlockingIOError:
                if self.timeout == 0.0:
                    raise
            self._wait(self._read_event)
        sock = socket(self.family, self.type, self.proto, fileno=fd)
        # Python Issue #7995: if no default timeout is set and the listening
        # socket had a (non-zero) timeout, force the new socket in blocking
        # mode to override platform-specific socket flags inheritance.
        # XXX do we need to do this?
        if getdefaulttimeout() is None and self.gettimeout():
            sock.setblocking(True)
        return sock, addr

    def makefile(self, mode="r", buffering=None, *,
                 encoding=None, errors=None, newline=None):
        """Return an I/O stream connected to the socket

        The arguments are as for io.open() after the filename,
        except the only mode characters supported are 'r', 'w' and 'b'.
        The semantics are similar too.
        """
        # (XXX refactor to share code?)
        for c in mode:
            if c not in {"r", "w", "b"}:
                raise ValueError("invalid mode %r (only r, w, b allowed)")
        writing = "w" in mode
        reading = "r" in mode or not writing
        assert reading or writing
        binary = "b" in mode
        rawmode = ""
        if reading:
            rawmode += "r"
        if writing:
            rawmode += "w"
        raw = SocketIO(self, rawmode)
        self._io_refs += 1
        if buffering is None:
            buffering = -1
        if buffering < 0:
            buffering = io.DEFAULT_BUFFER_SIZE
        if buffering == 0:
            if not binary:
                raise ValueError("unbuffered streams must be binary")
            return raw
        if reading and writing:
            buffer = io.BufferedRWPair(raw, raw, buffering)
        elif reading:
            buffer = io.BufferedReader(raw, buffering)
        else:
            assert writing
            buffer = io.BufferedWriter(raw, buffering)
        if binary:
            return buffer
        text = io.TextIOWrapper(buffer, encoding, errors, newline)
        text.mode = mode
        return text

    def _decref_socketios(self):
        # Called by SocketIO when it is closed.
        if self._io_refs > 0:
            self._io_refs -= 1
        if self._closed:
            self.close()

    def _drop_events(self, cancel_wait_ex=cancel_wait_ex):
        if self._read_event is not None:
            self.hub.cancel_wait(self._read_event, cancel_wait_ex, True)
            self._read_event = None
        if self._write_event is not None:
            self.hub.cancel_wait(self._write_event, cancel_wait_ex, True)
            self._write_event = None

    def _detach_socket(self, reason):
        if not self._sock:
            return

        # Break any reference to the loop.io objects. Our fileno,
        # which they were tied to, is about to be free to be reused, so these
        # objects are no longer functional.
        self._drop_events()

        # Break any references to the underlying socket object. Tested
        # by test__refcount. (Why does this matter?). Be sure to
        # preserve our same family/type/proto if possible (if we
        # don't, we can get TypeError instead of OSError; see
        # test_socket.SendmsgUDP6Test.testSendmsgAfterClose)... but
        # this isn't always possible (see test_socket.test_unknown_socket_family_repr)
        sock = self._sock
        family = -1
        type = -1
        proto = -1
        fileno = None
        try:
            family = sock.family
            type = sock.type
            proto = sock.proto
            fileno = sock.fileno()
        except OSError:
            pass

        self._sock = _closedsocket(family, type, proto, fileno, reason)

    def _real_close(self, _ss=_socket.socket):
        # This function should not reference any globals. See Python issue #808164.
        if not self._sock:
            return

        sock = self._sock
        try:
            self._detach_socket('closed')
        finally:
            sock.close()

    def close(self):
        # This function should not reference any globals. See Python issue #808164.
        self._closed = True
        if self._io_refs <= 0:
            self._real_close()

    @property
    def closed(self):
        return self._closed

    def detach(self):
        """
        detach() -> file descriptor

        Close the socket object without closing the underlying file
        descriptor. The object cannot be used after this call; when the
        real file descriptor is closed, the number that was previously
        used here may be reused. The fileno() method, after this call,
        will return an invalid socket id.

        The previous descriptor is returned.

        .. versionchanged:: 1.5

           Also immediately drop any native event loop resources.
        """
        self._closed = True
        sock = self._sock
        self._detach_socket('detached')
        return sock.detach()

    def connect(self, address):
        if self.timeout == 0.0:
            return _socket.socket.connect(self._sock, address)
        address = _socketcommon._resolve_addr(self._sock, address)

        with Timeout._start_new_or_dummy(self.timeout, timeout("timed out")):
            while True:
                err = self.getsockopt(SOL_SOCKET, SO_ERROR)
                if err:
                    raise error(err, strerror(err))
                result = _socket.socket.connect_ex(self._sock, address)

                if not result or result == EISCONN:
                    break
                elif (result in (EWOULDBLOCK, EINPROGRESS, EALREADY)) or (result == EINVAL and is_windows):
                    self._wait(self._write_event)
                else:
                    if (isinstance(address, tuple)
                            and address[0] == 'fe80::1'
                            and result == EHOSTUNREACH):
                        # On Python 3.7 on mac, we see EHOSTUNREACH
                        # returned for this link-local address, but it really is
                        # supposed to be ECONNREFUSED according to the standard library
                        # tests (test_socket.NetworkConnectionNoServer.test_create_connection)
                        # (On previous versions, that code passed the '127.0.0.1' IPv4 address, so
                        # ipv6 link locals were never a factor; 3.7 passes 'localhost'.)
                        # It is something of a mystery how the stdlib socket code doesn't
                        # produce EHOSTUNREACH---I (JAM) can't see how socketmodule.c would avoid
                        # that. The normal connect just calls connect_ex much like we do.
                        result = ECONNREFUSED
                    raise error(result, strerror(result))

    def connect_ex(self, address):
        try:
            return self.connect(address) or 0
        except timeout:
            return EAGAIN
        except gaierror: # pylint:disable=try-except-raise
            # gaierror/overflowerror/typerror is not silenced by connect_ex;
            # gaierror extends OSError (aka error) so catch it first
            raise
        except error as ex:
            # error is now OSError and it has various subclasses.
            # Only those that apply to actually connecting are silenced by
            # connect_ex.
            if ex.errno:
                return ex.errno
            raise # pragma: no cover

    def recv(self, *args):
        while True:
            try:
                return self._sock.recv(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    if hasattr(_socket.socket, 'recvmsg'):
        # Only on Unix; PyPy 3.5 5.10.0 provides sendmsg and recvmsg, but not
        # recvmsg_into (at least on os x)

        def recvmsg(self, *args):
            while True:
                try:
                    return self._sock.recvmsg(*args)
                except error as ex:
                    if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                        raise
                self._wait(self._read_event)

    if hasattr(_socket.socket, 'recvmsg_into'):

        def recvmsg_into(self, *args):
            while True:
                try:
                    return self._sock.recvmsg_into(*args)
                except error as ex:
                    if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                        raise
                self._wait(self._read_event)

    def recvfrom(self, *args):
        while True:
            try:
                return self._sock.recvfrom(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def recvfrom_into(self, *args):
        while True:
            try:
                return self._sock.recvfrom_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def recv_into(self, *args):
        while True:
            try:
                return self._sock.recv_into(*args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def send(self, data, flags=0, timeout=timeout_default):
        if timeout is timeout_default:
            timeout = self.timeout
        try:
            return self._sock.send(data, flags)
        except error as ex:
            if ex.args[0] not in _socketcommon.GSENDAGAIN or timeout == 0.0:
                raise
            self._wait(self._write_event)
            try:
                return _socket.socket.send(self._sock, data, flags)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def sendall(self, data, flags=0):
        # XXX Now that we run on PyPy3, see the notes in _socket2.py's sendall()
        # and implement that here if needed.
        # PyPy3 is not optimized for performance yet, and is known to be slower than
        # PyPy2, so it's possibly premature to do this. However, there is a 3.5 test case that
        # possibly exposes this in a severe way.
        data_memory = _get_memory(data)
        return _socketcommon._sendall(self, data_memory, flags)

    def sendto(self, *args):
        try:
            return self._sock.sendto(*args)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                raise
            self._wait(self._write_event)
            try:
                return self._sock.sendto(*args)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    if hasattr(_socket.socket, 'sendmsg'):
        # Only on Unix
        def sendmsg(self, buffers, ancdata=(), flags=0, address=None):
            try:
                return self._sock.sendmsg(buffers, ancdata, flags, address)
            except error as ex:
                if flags & getattr(_socket, 'MSG_DONTWAIT', 0):
                    # Enable non-blocking behaviour
                    # XXX: Do all platforms that have sendmsg have MSG_DONTWAIT?
                    raise

                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                self._wait(self._write_event)
                try:
                    return self._sock.sendmsg(buffers, ancdata, flags, address)
                except error as ex2:
                    if ex2.args[0] == EWOULDBLOCK:
                        return 0
                    raise

    def setblocking(self, flag):
        # Beginning in 3.6.0b3 this is supposed to raise
        # if the file descriptor is closed, but the test for it
        # involves closing the fileno directly. Since we
        # don't touch the fileno here, it doesn't make sense for
        # us.
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
        self.__dict__['timeout'] = howlong

    def gettimeout(self):
        return self.__dict__['timeout']

    def shutdown(self, how):
        if how == 0:  # SHUT_RD
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        elif how == 1:  # SHUT_WR
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        else:
            self.hub.cancel_wait(self._read_event, cancel_wait_ex)
            self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        self._sock.shutdown(how)

    # sendfile: new in 3.5. But there's no real reason to not
    # support it everywhere. Note that we can't use os.sendfile()
    # because it's not cooperative.
    def _sendfile_use_sendfile(self, file, offset=0, count=None):
        # This is called directly by tests
        raise __socket__._GiveupOnSendfile() # pylint:disable=no-member

    def _sendfile_use_send(self, file, offset=0, count=None):
        self._check_sendfile_params(file, offset, count)
        if self.gettimeout() == 0:
            raise ValueError("non-blocking sockets are not supported")
        if offset:
            file.seek(offset)
        blocksize = min(count, 8192) if count else 8192
        total_sent = 0
        # localize variable access to minimize overhead
        file_read = file.read
        sock_send = self.send
        try:
            while True:
                if count:
                    blocksize = min(count - total_sent, blocksize)
                    if blocksize <= 0:
                        break
                data = memoryview(file_read(blocksize))
                if not data:
                    break  # EOF
                while True:
                    try:
                        sent = sock_send(data)
                    except BlockingIOError:
                        continue
                    else:
                        total_sent += sent
                        if sent < len(data):
                            data = data[sent:]
                        else:
                            break
            return total_sent
        finally:
            if total_sent > 0 and hasattr(file, 'seek'):
                file.seek(offset + total_sent)

    def _check_sendfile_params(self, file, offset, count):
        if 'b' not in getattr(file, 'mode', 'b'):
            raise ValueError("file should be opened in binary mode")
        if not self.type & SOCK_STREAM:
            raise ValueError("only SOCK_STREAM type sockets are supported")
        if count is not None:
            if not isinstance(count, int):
                raise TypeError(
                    "count must be a positive integer (got {!r})".format(count))
            if count <= 0:
                raise ValueError(
                    "count must be a positive integer (got {!r})".format(count))

    def sendfile(self, file, offset=0, count=None):
        """sendfile(file[, offset[, count]]) -> sent

        Send a file until EOF is reached by using high-performance
        os.sendfile() and return the total number of bytes which
        were sent.
        *file* must be a regular file object opened in binary mode.
        If os.sendfile() is not available (e.g. Windows) or file is
        not a regular file socket.send() will be used instead.
        *offset* tells from where to start reading the file.
        If specified, *count* is the total number of bytes to transmit
        as opposed to sending the file until EOF is reached.
        File position is updated on return or also in case of error in
        which case file.tell() can be used to figure out the number of
        bytes which were sent.
        The socket must be of SOCK_STREAM type.
        Non-blocking sockets are not supported.

        .. versionadded:: 1.1rc4
           Added in Python 3.5, but available under all Python 3 versions in
           gevent.
        """
        return self._sendfile_use_send(file, offset, count)


    if os.name == 'nt':
        def get_inheritable(self):
            return os.get_handle_inheritable(self.fileno())

        def set_inheritable(self, inheritable):
            os.set_handle_inheritable(self.fileno(), inheritable)
    else:
        def get_inheritable(self):
            return os.get_inheritable(self.fileno())

        def set_inheritable(self, inheritable):
            os.set_inheritable(self.fileno(), inheritable)

    get_inheritable.__doc__ = "Get the inheritable flag of the socket"
    set_inheritable.__doc__ = "Set the inheritable flag of the socket"



SocketType = socket


def fromfd(fd, family, type, proto=0):
    """ fromfd(fd, family, type[, proto]) -> socket object

    Create a socket object from a duplicate of the given file
    descriptor.  The remaining arguments are the same as for socket().
    """
    nfd = dup(fd)
    return socket(family, type, proto, nfd)


if hasattr(_socket.socket, "share"):
    def fromshare(info):
        """ fromshare(info) -> socket object

        Create a socket object from a the bytes object returned by
        socket.share(pid).
        """
        return socket(0, 0, 0, info)

    __implements__.append('fromshare')


if hasattr(_socket, "socketpair"):

    def socketpair(family=None, type=SOCK_STREAM, proto=0):
        """socketpair([family[, type[, proto]]]) -> (socket object, socket object)

        Create a pair of socket objects from the sockets returned by the platform
        socketpair() function.
        The arguments are the same as for socket() except the default family is
        AF_UNIX if defined on the platform; otherwise, the default is AF_INET.

        .. versionchanged:: 1.2
           All Python 3 versions on Windows supply this function (natively
           supplied by Python 3.5 and above).
        """
        if family is None:
            try:
                family = AF_UNIX
            except NameError:
                family = AF_INET
        a, b = _socket.socketpair(family, type, proto)
        a = socket(family, type, proto, a.detach())
        b = socket(family, type, proto, b.detach())
        return a, b

else: # pragma: no cover
    # Origin: https://gist.github.com/4325783, by Geert Jansen.  Public domain.

    # gevent: taken from 3.6 release, confirmed unchanged in 3.7 and
    # 3.8a1. Expected to be used only on Win. Added to Win/3.5

    _LOCALHOST = '127.0.0.1'
    _LOCALHOST_V6 = '::1'

    def socketpair(family=AF_INET, type=SOCK_STREAM, proto=0):
        if family == AF_INET:
            host = _LOCALHOST
        elif family == AF_INET6:
            host = _LOCALHOST_V6
        else:
            raise ValueError("Only AF_INET and AF_INET6 socket address families "
                             "are supported")
        if type != SOCK_STREAM:
            raise ValueError("Only SOCK_STREAM socket type is supported")
        if proto != 0:
            raise ValueError("Only protocol zero is supported")

        # We create a connected TCP socket. Note the trick with
        # setblocking(False) that prevents us from having to create a thread.
        lsock = socket(family, type, proto)
        try:
            lsock.bind((host, 0))
            lsock.listen()
            # On IPv6, ignore flow_info and scope_id
            addr, port = lsock.getsockname()[:2]
            csock = socket(family, type, proto)
            try:
                csock.setblocking(False)
                try:
                    csock.connect((addr, port))
                except (BlockingIOError, InterruptedError):
                    pass
                csock.setblocking(True)
                ssock, _ = lsock.accept()
            except:
                csock.close()
                raise
        finally:
            lsock.close()
        return (ssock, csock)


if hasattr(__socket__, 'close'): # Python 3.7b1+
    close = __socket__.close # pylint:disable=no-member
    __imports__ += ['close']

__all__ = __implements__ + __extensions__ + __imports__
