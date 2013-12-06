# Wrapper module for _ssl. Written by Bill Janssen.
# Ported to gevent by Denis Bilenko.
"""SSL wrapper for socket objects.

For the documentation, refer to :mod:`ssl` module manual.

This module implements cooperative SSL socket wrappers.
"""

from __future__ import absolute_import
import ssl as __ssl__

try:
    _ssl = __ssl__._ssl
except AttributeError:
    _ssl = __ssl__._ssl2

import sys
import errno
from gevent.socket import socket, timeout_default
from gevent.socket import error as socket_error
from gevent.hub import integer_types
from gevent.hub import PY3
from gevent.hub import string_types


__implements__ = ['SSLSocket',
                  'wrap_socket',
                  'get_server_certificate',
                  'sslwrap_simple',
                  'SSLContext']

__imports__ = ['SSLError',
               'RAND_status',
               'RAND_egd',
               'RAND_add',
               'cert_time_to_seconds',
               'get_protocol_name',
               'DER_cert_to_PEM_cert',
               'PEM_cert_to_DER_cert',
               # Python 3
               'CHANNEL_BINDING_TYPES',
               'SSLZeroReturnError',
               'SSLWantReadError',
               'SSLWantWriteError',
               'SSLSyscallError',
               'SSLEOFError',
               'CertificateError',
               'RAND_bytes',
               'RAND_pseudo_bytes',
               'match_hostname']

for name in __imports__[:]:
    try:
        value = getattr(__ssl__, name)
        globals()[name] = value
    except AttributeError:
        __imports__.remove(name)

for name in dir(__ssl__):
    if not name.startswith('_'):
        value = getattr(__ssl__, name)
        if (isinstance(value, integer_types) or isinstance(value, tuple) or
                isinstance(value, string_types)):
            globals()[name] = value
            __imports__.append(name)

del name, value


class _BaseSSLSocket(socket):
    def _checkClosed(self, msg=None):
        # raise an exception here if you wish to check for spurious closes
        pass

    def write(self, data):
        """Write DATA to the underlying SSL channel.  Returns
        number of bytes of DATA actually transmitted."""

        self._checkClosed()
        while True:
            try:
                return self._sslobj.write(data)
            except SSLError as ex:
                if ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    event = self._read_event
                    timeout_exc = _SSLErrorWriteTimeout
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    event = self._write_event
                    timeout_exc = _SSLErrorWriteTimeout
                else:
                    raise
                if not PY3:
                    sys.exc_clear()
            self._wait(event, timeout_exc=timeout_exc)

    def getpeercert(self, binary_form=False):
        """Returns a formatted version of the data in the
        certificate provided by the other end of the SSL channel.
        Return None if no certificate was provided, {} if a
        certificate was provided, but not validated."""

        self._checkClosed()
        return self._sslobj.peer_certificate(binary_form)

    def cipher(self):
        self._checkClosed()
        if not self._sslobj:
            return None
        else:
            return self._sslobj.cipher()

    def send(self, data, flags=0, timeout=timeout_default):
        self._checkClosed()
        if timeout is timeout_default:
            timeout = self.timeout
        if self._sslobj:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to send() on %s" %
                    self.__class__)
            while True:
                try:
                    v = self._sslobj.write(data)
                except SSLError as x:
                    if x.args[0] == SSL_ERROR_WANT_READ:
                        if self.timeout == 0.0:
                            return 0
                        event = self._read_event
                    elif x.args[0] == SSL_ERROR_WANT_WRITE:
                        if self.timeout == 0.0:
                            return 0
                        event = self._write_event
                    else:
                        raise
                    if not PY3:
                        sys.exc_clear()
                else:
                    return v
                self._wait(event)
        else:
            return socket.send(self, data, flags, timeout)

    # is it possible for sendall() to send some data without encryption if another end shut down SSL?
    def sendall(self, data, flags=0):
        self._checkClosed()
        return socket.sendall(self, data, flags)

    def sendto(self, *args):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("sendto not allowed on instances of %s" %
                             self.__class__)
        else:
            return socket.sendto(self, *args)

    def recv(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to recv() on %s" %
                    self.__class__)
            # QQQ Shouldn't we wrap the SSL_WANT_READ errors as socket.timeout errors to match socket.recv's behavior?
            return self.read(buflen)
        else:
            return socket.recv(self, buflen, flags)

    def recvfrom(self, *args):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("recvfrom not allowed on instances of %s" %
                             self.__class__)
        else:
            return socket.recvfrom(self, *args)

    def recvfrom_into(self, *args):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("recvfrom_into not allowed on instances of %s" %
                             self.__class__)
        else:
            return socket.recvfrom_into(self, *args)

    def pending(self):
        self._checkClosed()
        if self._sslobj:
            return self._sslobj.pending()
        else:
            return 0

    def _sslobj_shutdown(self):
        while True:
            try:
                return self._sslobj.shutdown()
            except SSLError as ex:
                if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                    return ''
                elif ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    event = self._read_event
                    timeout_exc = _SSLErrorReadTimeout
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    event = self._write_event
                    timeout_exc = _SSLErrorWriteTimeout
                else:
                    raise
                if not PY3:
                    sys.exc_clear()
            self._wait(event, timeout_exc=timeout_exc)

    def unwrap(self):
        if self._sslobj:
            s = self._sslobj_shutdown()
            self._sslobj = None
            return socket(_sock=s)
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def shutdown(self, how):
        self._checkClosed()
        self._sslobj = None
        socket.shutdown(self, how)

    def do_handshake(self, block=False):
        """Perform a TLS/SSL handshake."""
        while True:
            try:
                return self._sslobj.do_handshake()
            except SSLError as ex:
                if ex.args[0] == SSL_ERROR_WANT_READ:
                    timeout = None
                    if self.timeout == 0.0:
                        if block:
                            timeout = (None,)
                        else:
                            raise
                    event = self._read_event
                    timeout_exc = _SSLErrorHandshakeTimeout
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    timeout = None
                    if self.timeout == 0.0:
                        if block:
                            timeout = (None,)
                        else:
                            raise
                    event = self._write_event
                    timeout_exc = _SSLErrorHandshakeTimeout
                else:
                    raise
                if not PY3:
                    sys.exc_clear()
            self._wait(event, timeout_exc=timeout_exc, timeout=timeout)


if PY3:
    class SSLContext(__ssl__.SSLContext):
        """An SSLContext holds various SSL-related configuration options and
        data, such as certificates and possibly a private key."""

        def wrap_socket(self, sock, server_side=False,
                        do_handshake_on_connect=True,
                        suppress_ragged_eofs=True,
                        server_hostname=None):
            return SSLSocket(sock=sock, server_side=server_side,
                             do_handshake_on_connect=do_handshake_on_connect,
                             suppress_ragged_eofs=suppress_ragged_eofs,
                             server_hostname=server_hostname,
                             _context=self)

    class SSLSocket(_BaseSSLSocket):
        def __init__(self, sock=None, keyfile=None, certfile=None,
                     server_side=False, cert_reqs=CERT_NONE,
                     ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                     do_handshake_on_connect=True,
                     family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None,
                     suppress_ragged_eofs=True, npn_protocols=None,
                     ciphers=None, server_hostname=None,
                     _context=None):
            if _context:
                self.context = _context
            else:
                if server_side and not certfile:
                    raise ValueError("certfile must be specified for server-side "
                                     "operations")
                if keyfile and not certfile:
                    raise ValueError("certfile must be specified")
                if certfile and not keyfile:
                    keyfile = certfile
                self.context = SSLContext(ssl_version)
                self.context.verify_mode = cert_reqs
                if ca_certs:
                    self.context.load_verify_locations(ca_certs)
                if certfile:
                    self.context.load_cert_chain(certfile, keyfile)
                if npn_protocols:
                    self.context.set_npn_protocols(npn_protocols)
                if ciphers:
                    self.context.set_ciphers(ciphers)
                self.keyfile = keyfile
                self.certfile = certfile
                self.cert_reqs = cert_reqs
                self.ssl_version = ssl_version
                self.ca_certs = ca_certs
                self.ciphers = ciphers
            if server_side and server_hostname:
                raise ValueError("server_hostname can only be specified "
                                 "in client mode")
            self.server_side = server_side
            self.server_hostname = server_hostname
            self.do_handshake_on_connect = do_handshake_on_connect
            self.suppress_ragged_eofs = suppress_ragged_eofs
            connected = False
            if sock is not None:
                socket.__init__(self,
                                family=sock.family,
                                type=sock.type,
                                proto=sock.proto,
                                fileno=sock.fileno())
                self.settimeout(sock.gettimeout())
                # see if it's connected
                try:
                    sock.getpeername()
                except socket_error as e:
                    if e.errno != errno.ENOTCONN:
                        raise
                else:
                    connected = True
                sock.detach()
            elif fileno is not None:
                socket.__init__(self, fileno=fileno)
            else:
                socket.__init__(self, family=family, type=type, proto=proto)

            self._closed = False
            self._sslobj = None
            self._connected = connected
            if connected:
                # create the SSL object
                try:
                    self._sslobj = self.context._wrap_socket(self, server_side,
                                                             server_hostname)
                    if do_handshake_on_connect:
                        timeout = self.gettimeout()
                        if timeout == 0.0:
                            # non-blocking
                            raise ValueError("do_handshake_on_connect should not be specified for non-blocking sockets")
                        self.do_handshake()

                except socket_error as x:
                    self.close()
                    raise x

        def dup(self):
            raise NotImplemented("Can't dup() %s instances" %
                                 self.__class__.__name__)

        def read(self, len=0, buffer=None):
            """Read up to LEN bytes and return them.
            Return zero-length string on EOF."""

            self._checkClosed()  # QQQ: maybe check in while?
            while True:
                try:
                    if buffer is not None:
                        v = self._sslobj.read(len, buffer)
                    else:
                        v = self._sslobj.read(len or 1024)
                    return v
                except SSLError as ex:
                    if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                        if buffer is not None:
                            return 0
                        else:
                            return b''
                    elif ex.args[0] == SSL_ERROR_WANT_READ:
                        if self.timeout == 0.0:
                            raise
                        event = self._read_event
                        timeout_exc = _SSLErrorReadTimeout
                    elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                        if self.timeout == 0.0:
                            raise
                        # note: using _SSLErrorReadTimeout rather than _SSLErrorWriteTimeout below is intentional
                        event = self._write_event
                        timeout_exc = _SSLErrorReadTimeout
                    else:
                        raise
                self._wait(event, timeout_exc=timeout_exc)

        def compression(self):
            self._checkClosed()
            if not self._sslobj:
                return None
            else:
                return self._sslobj.compression()

        def sendmsg(self, *args, **kwargs):
            # Ensure programs don't send data unencrypted if they try to
            # use this method.
            raise NotImplementedError("sendmsg not allowed on instances of %s" %
                                      self.__class__)

        def recv_into(self, buffer, nbytes=None, flags=0):
            self._checkClosed()
            if buffer and (nbytes is None):
                nbytes = len(buffer)
            elif nbytes is None:
                nbytes = 1024
            if self._sslobj:
                if flags != 0:
                    raise ValueError(
                        "non-zero flags not allowed in calls to recv_into() on %s" %
                        self.__class__)
                while True:
                    try:
                        return self.read(nbytes, buffer)
                    except SSLError as x:
                        if x.args[0] == SSL_ERROR_WANT_READ:
                            if self.timeout == 0.0:
                                raise
                        else:
                            raise
                    self._wait(self._read_event)
            else:
                return socket.recv_into(self, buffer, nbytes, flags)

        def recvmsg(self, *args, **kwargs):
            raise NotImplementedError("recvmsg not allowed on instances of %s" %
                                      self.__class__)

        def recvmsg_into(self, *args, **kwargs):
            raise NotImplementedError("recvmsg_into not allowed on instances of "
                                      "%s" % self.__class__)

        def _real_close(self):
            self._sslobj = None
            # self._closed = True
            socket._real_close(self)

        def _real_connect(self, addr, connect_ex):
            if self.server_side:
                raise ValueError("can't connect in server-side mode")
            # Here we assume that the socket is client-side, and not
            # connected at the time of the call.  We connect it, then wrap it.
            if self._connected:
                raise ValueError("attempt to connect already-connected SSLSocket!")
            self._sslobj = self.context._wrap_socket(self, False, self.server_hostname)
            try:
                if connect_ex:
                    rc = socket.connect_ex(self, addr)
                else:
                    rc = None
                    socket.connect(self, addr)
                if not rc:
                    if self.do_handshake_on_connect:
                        self.do_handshake()
                    self._connected = True
                return rc
            except socket_error:
                self._sslobj = None
                raise

        def connect(self, addr):
            """Connects to remote ADDR, and then wraps the connection in
            an SSL channel."""
            self._real_connect(addr, False)

        def connect_ex(self, addr):
            """Connects to remote ADDR, and then wraps the connection in
            an SSL channel."""
            return self._real_connect(addr, True)

        def accept(self):
            """Accepts a new connection from a remote client, and returns
            a tuple containing that new connection wrapped with a server-side
            SSL channel, and the address of the remote client."""

            newsock, addr = socket.accept(self)
            newsock = self.context.wrap_socket(
                newsock,
                do_handshake_on_connect=self.do_handshake_on_connect,
                suppress_ragged_eofs=self.suppress_ragged_eofs,
                server_side=True)
            return newsock, addr

        def get_channel_binding(self, cb_type="tls-unique"):
            """Get channel binding data for current connection.  Raise ValueError
            if the requested `cb_type` is not supported.  Return bytes of the data
            or None if the data is not available (e.g. before the handshake).
            """
            if cb_type not in CHANNEL_BINDING_TYPES:
                raise ValueError("Unsupported channel binding type")
            if cb_type != "tls-unique":
                raise NotImplementedError(
                    "{0} channel binding type not implemented"
                    .format(cb_type))
            if self._sslobj is None:
                return None
            return self._sslobj.tls_unique_cb()

else:
    from gevent.socket import _fileobject

    __implements__.remove('SSLContext')

    class SSLSocket(_BaseSSLSocket):
        def __init__(self, sock, keyfile=None, certfile=None,
                     server_side=False, cert_reqs=CERT_NONE,
                     ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                     do_handshake_on_connect=True, suppress_ragged_eofs=True,
                     ciphers=None):
            socket.__init__(self, _sock=sock)

            if certfile and not keyfile:
                keyfile = certfile
                # see if it's connected
            try:
                socket.getpeername(self)
            except socket_error as e:
                if e[0] != errno.ENOTCONN:
                    raise
                    # no, no connection yet
                self._sslobj = None
            else:
                # yes, create the SSL object
                if ciphers is None:
                    self._sslobj = _ssl.sslwrap(self._sock, server_side,
                                                keyfile, certfile,
                                                cert_reqs, ssl_version, ca_certs)
                else:
                    self._sslobj = _ssl.sslwrap(self._sock, server_side,
                                                keyfile, certfile,
                                                cert_reqs, ssl_version, ca_certs,
                                                ciphers)
                if do_handshake_on_connect:
                    self.do_handshake()
            self.keyfile = keyfile
            self.certfile = certfile
            self.cert_reqs = cert_reqs
            self.ssl_version = ssl_version
            self.ca_certs = ca_certs
            self.ciphers = ciphers
            self.do_handshake_on_connect = do_handshake_on_connect
            self.suppress_ragged_eofs = suppress_ragged_eofs
            self._makefile_refs = 0

        def read(self, len=1024):
            """Read up to LEN bytes and return them.
            Return zero-length string on EOF."""

            self._checkClosed()
            while True:
                try:
                    return self._sslobj.read(len)
                except SSLError as ex:
                    if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                        return ''
                    elif ex.args[0] == SSL_ERROR_WANT_READ:
                        if self.timeout == 0.0:
                            raise
                        sys.exc_clear()
                        self._wait(self._read_event, timeout_exc=_SSLErrorReadTimeout)
                    elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                        if self.timeout == 0.0:
                            raise
                        sys.exc_clear()
                        # note: using _SSLErrorReadTimeout rather than _SSLErrorWriteTimeout below is intentional
                        self._wait(self._write_event, timeout_exc=_SSLErrorReadTimeout)
                    else:
                        raise

        def recv_into(self, buffer, nbytes=None, flags=0):
            self._checkClosed()
            if buffer and (nbytes is None):
                nbytes = len(buffer)
            elif nbytes is None:
                nbytes = 1024
            if self._sslobj:
                if flags != 0:
                    raise ValueError(
                        "non-zero flags not allowed in calls to recv_into() on %s" %
                        self.__class__)
                while True:
                    try:
                        tmp_buffer = self.read(nbytes)
                        v = len(tmp_buffer)
                        buffer[:v] = tmp_buffer
                        return v
                    except SSLError as x:
                        if x.args[0] == SSL_ERROR_WANT_READ:
                            if self.timeout == 0.0:
                                raise
                            sys.exc_clear()
                            self._wait(self._read_event)
                            continue
                        else:
                            raise
            else:
                return socket.recv_into(self, buffer, nbytes, flags)

        def close(self):
            if self._makefile_refs < 1:
                self._sslobj = None
                socket.close(self)
            else:
                self._makefile_refs -= 1

        def connect(self, addr):
            """Connects to remote ADDR, and then wraps the connection in
            an SSL channel."""
            # Here we assume that the socket is client-side, and not
            # connected at the time of the call.  We connect it, then wrap it.
            if self._sslobj:
                raise ValueError("attempt to connect already-connected SSLSocket!")
            socket.connect(self, addr)
            if self.ciphers is None:
                self._sslobj = _ssl.sslwrap(self._sock, False, self.keyfile, self.certfile,
                                            self.cert_reqs, self.ssl_version,
                                            self.ca_certs)
            else:
                self._sslobj = _ssl.sslwrap(self._sock, False, self.keyfile, self.certfile,
                                            self.cert_reqs, self.ssl_version,
                                            self.ca_certs, self.ciphers)
            if self.do_handshake_on_connect:
                self.do_handshake()

        def accept(self):
            """Accepts a new connection from a remote client, and returns
            a tuple containing that new connection wrapped with a server-side
            SSL channel, and the address of the remote client."""
            newsock, addr = socket.accept(self)
            return (SSLSocket(newsock._sock,
                              keyfile=self.keyfile,
                              certfile=self.certfile,
                              server_side=True,
                              cert_reqs=self.cert_reqs,
                              ssl_version=self.ssl_version,
                              ca_certs=self.ca_certs,
                              do_handshake_on_connect=self.do_handshake_on_connect,
                              suppress_ragged_eofs=self.suppress_ragged_eofs,
                              ciphers=self.ciphers),
                    addr)

        def makefile(self, mode='r', bufsize=-1):
            """Make and return a file-like object that
            works with the SSL connection.  Just use the code
            from the socket module."""
            self._makefile_refs += 1
            # close=True so as to decrement the reference count when done with
            # the file-like object.
            return _fileobject(self, mode, bufsize, close=True)


_SSLErrorReadTimeout = SSLError('The read operation timed out')
_SSLErrorWriteTimeout = SSLError('The write operation timed out')
_SSLErrorHandshakeTimeout = SSLError('The handshake operation timed out')


def wrap_socket(sock, keyfile=None, certfile=None,
                server_side=False, cert_reqs=CERT_NONE,
                ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                do_handshake_on_connect=True,
                suppress_ragged_eofs=True, ciphers=None):
    """Create a new :class:`SSLSocket` instance."""
    return SSLSocket(sock, keyfile=keyfile, certfile=certfile,
                     server_side=server_side, cert_reqs=cert_reqs,
                     ssl_version=ssl_version, ca_certs=ca_certs,
                     do_handshake_on_connect=do_handshake_on_connect,
                     suppress_ragged_eofs=suppress_ragged_eofs,
                     ciphers=ciphers)


def get_server_certificate(addr, ssl_version=PROTOCOL_SSLv3, ca_certs=None):
    """Retrieve the certificate from the server at the specified address,
    and return it as a PEM-encoded string.
    If 'ca_certs' is specified, validate the server cert against it.
    If 'ssl_version' is specified, use it in the connection attempt."""

    host, port = addr
    if (ca_certs is not None):
        cert_reqs = CERT_REQUIRED
    else:
        cert_reqs = CERT_NONE
    s = wrap_socket(socket(), ssl_version=ssl_version,
                    cert_reqs=cert_reqs, ca_certs=ca_certs)
    s.connect(addr)
    dercert = s.getpeercert(True)
    s.close()
    return DER_cert_to_PEM_cert(dercert)


if PY3:
    __implements__.remove('sslwrap_simple')
else:
    def sslwrap_simple(sock, keyfile=None, certfile=None):
        """A replacement for the old socket.ssl function.  Designed
        for compability with Python 2.5 and earlier.  Will disappear in
        Python 3.0."""
        return SSLSocket(sock, keyfile, certfile)


__all__ = __implements__ + __imports__
