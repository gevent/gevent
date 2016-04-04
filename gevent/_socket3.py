# Port of Python 3.3's socket module to gevent
"""
Python 3 socket module.
"""
import io
import os
import sys
import time
from gevent import _socketcommon
import _socket
from os import dup

for key in _socketcommon.__dict__:
    if key.startswith('__') or key in _socketcommon.__extensions__:
        continue
    globals()[key] = getattr(_socketcommon, key)

__socket__ = _socketcommon.__socket__
__implements__ = _socketcommon._implements
__extensions__ = _socketcommon.__extensions__
__imports__ = _socketcommon.__imports__
__dns__ = _socketcommon.__dns__


SocketIO = __socket__.SocketIO


def _get_memory(data):
    mv = memoryview(data)
    if mv.shape:
        return mv
    # No shape, probably working with a ctypes object,
    # or something else exotic that supports the buffer interface
    return mv.tobytes()

timeout_default = object()


class _wrefsocket(_socket.socket):
    # Plain stdlib socket.socket objects subclass _socket.socket
    # and add weakref ability. The ssl module, for one, counts on this.
    # We don't create socket.socket objects (because they may have been
    # monkey patched to be the object from this module), but we still
    # need to make sure what we do create can be weakrefd.

    __slots__ = ("__weakref__", )


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

    def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
        # Take the same approach as socket2: wrap a real socket object,
        # don't subclass it. This lets code that needs the raw _sock (not tied to the hub)
        # get it. This shows up in tests like test__example_udp_server.
        self._sock = self._gevent_sock_class(family, type, proto, fileno)
        self._io_refs = 0
        self._closed = False
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
                return self._sock.type & ~_socket.SOCK_NONBLOCK
            else:
                return self._sock.type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self._closed:
            self.close()

    def __repr__(self):
        """Wrap __repr__() to reveal the real class name."""
        try:
            s = _socket.socket.__repr__(self._sock)
        except Exception as ex:
            # Observed on Windows Py3.3, printing the repr of a socket
            # that just sufferred a ConnectionResetError [WinError 10054]:
            # "OverflowError: no printf formatter to display the socket descriptor in decimal"
            # Not sure what the actual cause is or if there's a better way to handle this
            s = '<socket [%r]>' % ex

        if s.startswith("<socket object"):
            s = "<%s.%s%s%s" % (self.__class__.__module__,
                                self.__class__.__name__,
                                getattr(self, '_closed', False) and " [closed] " or "",
                                s[7:])
        return s

    def __getstate__(self):
        raise TypeError("Cannot serialize socket object")

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
        if watcher.callback is not None:
            raise _socketcommon.ConcurrentObjectUseError('This socket is already used by another greenlet: %r' % (watcher.callback, ))
        if self.timeout is not None:
            timeout = Timeout.start_new(self.timeout, timeout_exc, ref=False)
        else:
            timeout = None
        try:
            self.hub.wait(watcher)
        finally:
            if timeout is not None:
                timeout.cancel()

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
        if self._io_refs > 0:
            self._io_refs -= 1
        if self._closed:
            self.close()

    def _real_close(self, _ss=_socket.socket, cancel_wait_ex=cancel_wait_ex):
        # This function should not reference any globals. See Python issue #808164.
        self.hub.cancel_wait(self._read_event, cancel_wait_ex)
        self.hub.cancel_wait(self._write_event, cancel_wait_ex)
        _ss.close(self._sock)

        # Break any references to the underlying socket object. Tested
        # by test__refcount. (Why does this matter?). Be sure to
        # preserve our same family/type/proto if possible (if we
        # don't, we can get TypeError instead of OSError; see
        # test_socket.SendmsgUDP6Test.testSendmsgAfterClose)... but
        # this isn't always possible (see test_socket.test_unknown_socket_family_repr)
        # TODO: Can we use a simpler proxy, like _socket2 does?
        try:
            self._sock = self._gevent_sock_class(self.family, self.type, self.proto)
        except OSError:
            pass
        else:
            _ss.close(self._sock)

    def close(self):
        # This function should not reference any globals. See Python issue #808164.
        self._closed = True
        if self._io_refs <= 0:
            self._real_close()

    @property
    def closed(self):
        return self._closed

    def detach(self):
        """detach() -> file descriptor

        Close the socket object without closing the underlying file descriptor.
        The object cannot be used after this call, but the file descriptor
        can be reused for other purposes.  The file descriptor is returned.
        """
        self._closed = True
        return self._sock.detach()

    def connect(self, address):
        if self.timeout == 0.0:
            return _socket.socket.connect(self._sock, address)
        if isinstance(address, tuple):
            r = getaddrinfo(address[0], address[1], self.family)
            address = r[0][-1]
        if self.timeout is not None:
            timer = Timeout.start_new(self.timeout, timeout('timed out'))
        else:
            timer = None
        try:
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

    def recv(self, *args):
        while True:
            try:
                return _socket.socket.recv(self._sock, *args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    if hasattr(_socket.socket, 'sendmsg'):
        # Only on Unix

        def recvmsg(self, *args):
            while True:
                try:
                    return _socket.socket.recvmsg(self._sock, *args)
                except error as ex:
                    if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                        raise
                self._wait(self._read_event)

        def recvmsg_into(self, *args):
            while True:
                try:
                    return _socket.socket.recvmsg_into(self._sock, *args)
                except error as ex:
                    if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                        raise
                self._wait(self._read_event)

    def recvfrom(self, *args):
        while True:
            try:
                return _socket.socket.recvfrom(self._sock, *args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def recvfrom_into(self, *args):
        while True:
            try:
                return _socket.socket.recvfrom_into(self._sock, *args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def recv_into(self, *args):
        while True:
            try:
                return _socket.socket.recv_into(self._sock, *args)
            except error as ex:
                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
            self._wait(self._read_event)

    def send(self, data, flags=0, timeout=timeout_default):
        if timeout is timeout_default:
            timeout = self.timeout
        try:
            return _socket.socket.send(self._sock, data, flags)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or timeout == 0.0:
                raise
            self._wait(self._write_event)
            try:
                return _socket.socket.send(self._sock, data, flags)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    def sendall(self, data, flags=0):
        # XXX When we run on PyPy3, see the notes in _socket2.py's sendall()
        data_memory = _get_memory(data)
        len_data_memory = len(data_memory)
        if not len_data_memory:
            # Don't try to send empty data at all, no point, and breaks ssl
            # See issue 719
            return 0

        if self.timeout is None:
            data_sent = 0
            while data_sent < len_data_memory:
                data_sent += self.send(data_memory[data_sent:], flags)
        else:
            timeleft = self.timeout
            end = time.time() + timeleft
            data_sent = 0
            while True:
                data_sent += self.send(data_memory[data_sent:], flags, timeout=timeleft)
                if data_sent >= len_data_memory:
                    break
                timeleft = end - time.time()
                if timeleft <= 0:
                    raise timeout('timed out')

    def sendto(self, *args):
        try:
            return _socket.socket.sendto(self._sock, *args)
        except error as ex:
            if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                raise
            self._wait(self._write_event)
            try:
                return _socket.socket.sendto(self._sock, *args)
            except error as ex2:
                if ex2.args[0] == EWOULDBLOCK:
                    return 0
                raise

    if hasattr(_socket.socket, 'sendmsg'):
        # Only on Unix
        def sendmsg(self, buffers, ancdata=(), flags=0, address=None):
            try:
                return _socket.socket.sendmsg(self._sock, buffers, ancdata, flags, address)
            except error as ex:
                if flags & getattr(_socket, 'MSG_DONTWAIT', 0):
                    # Enable non-blocking behaviour
                    # XXX: Do all platforms that have sendmsg have MSG_DONTWAIT?
                    raise

                if ex.args[0] != EWOULDBLOCK or self.timeout == 0.0:
                    raise
                self._wait(self._write_event)
                try:
                    return _socket.socket.sendmsg(self._sock, buffers, ancdata, flags, address)
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
        self.timeout = howlong

    def gettimeout(self):
        return self.timeout

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
        raise __socket__._GiveupOnSendfile()

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

    # get/set_inheritable new in 3.4
    if hasattr(os, 'get_inheritable') or hasattr(os, 'get_handle_inheritable'):
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
        _added = "\n\n.. versionadded:: 1.1rc4 Added in Python 3.4"
        get_inheritable.__doc__ = "Get the inheritable flag of the socket" + _added
        set_inheritable.__doc__ = "Set the inheritable flag of the socket" + _added
        del _added


if sys.version_info[:2] == (3, 4) and sys.version_info[:3] <= (3, 4, 2):
    # Python 3.4, up to and including 3.4.2, had a bug where the
    # SocketType enumeration overwrote the SocketType class imported
    # from _socket. This was fixed in 3.4.3 (http://bugs.python.org/issue20386
    # and https://github.com/python/cpython/commit/0d2f85f38a9691efdfd1e7285c4262cab7f17db7).
    # Prior to that, if we replace SocketType with our own class, the implementation
    # of socket.type breaks with "OSError: [Errno 97] Address family not supported by protocol".
    # Therefore, on these old versions, we must preserve it as an enum; while this
    # seems like it could lead to non-green behaviour, code on those versions
    # cannot possibly be using SocketType as a class anyway.
    SocketType = __socket__.SocketType
    # Fixup __all__; note that we get exec'd multiple times during unit tests
    if 'SocketType' in __implements__:
        __implements__.remove('SocketType')
    if 'SocketType' not in __imports__:
        __imports__.append('SocketType')
else:
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

elif 'socketpair' in __implements__:
    # Win32: not available
    # Multiple imports can cause this to be missing if _socketcommon
    # was successfully imported, leading to subsequent imports to cause
    # ValueError
    __implements__.remove('socketpair')


# PyPy needs drop and reuse
def _do_reuse_or_drop(socket, methname):
    try:
        method = getattr(socket, methname)
    except (AttributeError, TypeError):
        pass
    else:
        method()

from io import BytesIO


class _basefileobject(object):
    """Faux file object attached to a socket object."""

    default_bufsize = 8192
    name = "<socket>"

    __slots__ = ["mode", "bufsize", "softspace",
                 # "closed" is a property, see below
                 "_sock", "_rbufsize", "_wbufsize", "_rbuf", "_wbuf", "_wbuf_len",
                 "_close"]

    def __init__(self, sock, mode='rb', bufsize=-1, close=False):
        _do_reuse_or_drop(sock, '_reuse')
        self._sock = sock
        self.mode = mode # Not actually used in this version
        if bufsize < 0:
            bufsize = self.default_bufsize
        self.bufsize = bufsize
        self.softspace = False
        # _rbufsize is the suggested recv buffer size.  It is *strictly*
        # obeyed within readline() for recv calls.  If it is larger than
        # default_bufsize it will be used for recv calls within read().
        if bufsize == 0:
            self._rbufsize = 1
        elif bufsize == 1:
            self._rbufsize = self.default_bufsize
        else:
            self._rbufsize = bufsize
        self._wbufsize = bufsize
        # We use BytesIO for the read buffer to avoid holding a list
        # of variously sized string objects which have been known to
        # fragment the heap due to how they are malloc()ed and often
        # realloc()ed down much smaller than their original allocation.
        self._rbuf = BytesIO()
        self._wbuf = [] # A list of strings
        self._wbuf_len = 0
        self._close = close

    def _getclosed(self):
        return self._sock is None
    closed = property(_getclosed, doc="True if the file is closed")

    def close(self):
        try:
            if self._sock:
                self.flush()
        finally:
            s = self._sock
            self._sock = None
            if s is not None:
                if self._close:
                    s.close()
                else:
                    _do_reuse_or_drop(s, '_drop')

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    def flush(self):
        if self._wbuf:
            data = b"".join(self._wbuf)
            self._wbuf = []
            self._wbuf_len = 0
            buffer_size = max(self._rbufsize, self.default_bufsize)
            data_size = len(data)
            write_offset = 0
            view = memoryview(data)
            try:
                while write_offset < data_size:
                    self._sock.sendall(view[write_offset:write_offset + buffer_size])
                    write_offset += buffer_size
            finally:
                if write_offset < data_size:
                    remainder = data[write_offset:]
                    del view, data  # explicit free
                    self._wbuf.append(remainder)
                    self._wbuf_len = len(remainder)

    def fileno(self):
        return self._sock.fileno()

    def write(self, data):
        if not isinstance(data, bytes):
            raise TypeError("Non-bytes data")
        if not data:
            return
        self._wbuf.append(data)
        self._wbuf_len += len(data)
        if (self._wbufsize == 0 or (self._wbufsize == 1 and b'\n' in data) or
            (self._wbufsize > 1 and self._wbuf_len >= self._wbufsize)):
            self.flush()

    def writelines(self, list):
        # XXX We could do better here for very long lists
        # XXX Should really reject non-string non-buffers
        lines = filter(None, map(str, list))
        self._wbuf_len += sum(map(len, lines))
        self._wbuf.extend(lines)
        if (self._wbufsize <= 1 or self._wbuf_len >= self._wbufsize):
            self.flush()

    def read(self, size=-1):
        # Use max, disallow tiny reads in a loop as they are very inefficient.
        # We never leave read() with any leftover data from a new recv() call
        # in our internal buffer.
        rbufsize = max(self._rbufsize, self.default_bufsize)
        # Our use of BytesIO rather than lists of string objects returned by
        # recv() minimizes memory usage and fragmentation that occurs when
        # rbufsize is large compared to the typical return value of recv().
        buf = self._rbuf
        buf.seek(0, 2)  # seek end
        if size < 0:
            # Read until EOF
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                try:
                    data = self._sock.recv(rbufsize)
                except InterruptedError:
                    continue
                if not data:
                    break
                buf.write(data)
            return buf.getvalue()
        else:
            # Read until size bytes or EOF seen, whichever comes first
            buf_len = buf.tell()
            if buf_len >= size:
                # Already have size bytes in our buffer?  Extract and return.
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return rv

            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                left = size - buf_len
                # recv() will malloc the amount of memory given as its
                # parameter even though it often returns much less data
                # than that.  The returned data string is short lived
                # as we copy it into a BytesIO and free it.  This avoids
                # fragmentation issues on many platforms.
                try:
                    data = self._sock.recv(left)
                except InterruptedError:
                    continue

                if not data:
                    break
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid buffer data copies when:
                    # - We have no data in our buffer.
                    # AND
                    # - Our call to recv returned exactly the
                    #   number of bytes we were asked to read.
                    return data
                if n == left:
                    buf.write(data)
                    del data  # explicit free
                    break
                assert n <= left, "recv(%d) returned %d bytes" % (left, n)
                buf.write(data)
                buf_len += n
                del data  # explicit free
                #assert buf_len == buf.tell()
            return buf.getvalue()

    def readline(self, size=-1):
        buf = self._rbuf
        buf.seek(0, 2)  # seek end
        if buf.tell() > 0:
            # check if we already have it in our buffer
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith(b'\n') or len(bline) == size:
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return bline
            del bline
        if size < 0:
            # Read until \n or EOF, whichever comes first
            if self._rbufsize <= 1:
                # Speed up unbuffered case
                buf.seek(0)
                buffers = [buf.read()]
                self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
                data = None
                recv = self._sock.recv
                while True:
                    try:
                        while data != b"\n":
                            data = recv(1)
                            if not data:
                                break
                            buffers.append(data)
                    except InterruptedError:
                        # The try..except to catch EINTR was moved outside the
                        # recv loop to avoid the per byte overhead.
                        continue

                    break
                return b"".join(buffers)

            buf.seek(0, 2)  # seek end
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                try:
                    data = self._sock.recv(self._rbufsize)
                except InterruptedError:
                    continue

                if not data:
                    break
                nl = data.find(b'\n')
                if nl >= 0:
                    nl += 1
                    buf.write(data[:nl])
                    self._rbuf.write(data[nl:])
                    del data
                    break
                buf.write(data)
            return buf.getvalue()
        else:
            # Read until size bytes or \n or EOF seen, whichever comes first
            buf.seek(0, 2)  # seek end
            buf_len = buf.tell()
            if buf_len >= size:
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = BytesIO()
                self._rbuf.write(buf.read())
                return rv
            self._rbuf = BytesIO()  # reset _rbuf.  we consume it via buf.
            while True:
                try:
                    data = self._sock.recv(self._rbufsize)
                except InterruptedError:
                    continue

                if not data:
                    break
                left = size - buf_len
                # did we just receive a newline?
                nl = data.find(b'\n', 0, left)
                if nl >= 0:
                    nl += 1
                    # save the excess data to _rbuf
                    self._rbuf.write(data[nl:])
                    if buf_len:
                        buf.write(data[:nl])
                        break
                    else:
                        # Shortcut.  Avoid data copy through buf when returning
                        # a substring of our first recv().
                        return data[:nl]
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid data copy through buf when
                    # returning exactly all of our first recv().
                    return data
                if n >= left:
                    buf.write(data[:left])
                    self._rbuf.write(data[left:])
                    break
                buf.write(data)
                buf_len += n
                #assert buf_len == buf.tell()
            return buf.getvalue()

    def readlines(self, sizehint=0):
        total = 0
        list = []
        while True:
            line = self.readline()
            if not line:
                break
            list.append(line)
            total += len(line)
            if sizehint and total >= sizehint:
                break
        return list

    # Iterator protocols

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line
    __next__ = next

try:
    from gevent.fileobject import FileObjectPosix
except ImportError:
    # Manual implementation
    _fileobject = _basefileobject
else:
    class _fileobject(FileObjectPosix):
        # Add the proper drop/reuse support for pypy, and match
        # the close=False default in the constructor
        def __init__(self, sock, mode='rb', bufsize=-1, close=False):
            _do_reuse_or_drop(sock, '_reuse')
            self._sock = sock
            FileObjectPosix.__init__(self, sock, mode, bufsize, close)

        def close(self):
            try:
                if self._sock:
                    self.flush()
            finally:
                s = self._sock
                self._sock = None
                if s is not None:
                    if self._close:
                        FileObjectPosix.close(self)
                    else:
                        _do_reuse_or_drop(s, '_drop')

        def __del__(self):
            try:
                self.close()
            except:
                # close() may fail if __init__ didn't complete
                pass


__all__ = __implements__ + __extensions__ + __imports__
