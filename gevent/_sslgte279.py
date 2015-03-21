# Wrapper module for _ssl. Written by Bill Janssen.
# Ported to gevent by Denis Bilenko.
"""SSL wrapper for socket objects.

For the documentation, refer to :mod:`ssl` module manual.

This module implements cooperative SSL socket wrappers.
"""

from __future__ import absolute_import
import ssl as __ssl__

_ssl = __ssl__._ssl

import errno
from gevent.socket import socket, timeout_default
from gevent.socket import error as socket_error


__implements__ = ['SSLContext',
                  'SSLSocket',
                  'wrap_socket',
                  'get_server_certificate']


# Import all symbols from Python's ssl.py, except those that we are implementing
# and "private" symbols.
for name in dir(__ssl__):
    if name in __implements__:
        continue
    if name.startswith('__'):
        continue
    value = getattr(__ssl__, name)
    globals()[name] = value


del name, value


orig_SSLContext = __ssl__.SSLContext


class SSLContext(orig_SSLContext):
    def wrap_socket(self, sock, server_side=False,
                    do_handshake_on_connect=True,
                    suppress_ragged_eofs=True,
                    server_hostname=None):
        return SSLSocket(sock=sock, server_side=server_side,
                         do_handshake_on_connect=do_handshake_on_connect,
                         suppress_ragged_eofs=suppress_ragged_eofs,
                         server_hostname=server_hostname,
                         _context=self)


def create_default_context(purpose=Purpose.SERVER_AUTH, cafile=None,
                           capath=None, cadata=None):
    """Create a SSLContext object with default settings.

    NOTE: The protocol and settings may change anytime without prior
          deprecation. The values represent a fair balance between maximum
          compatibility and security.
    """
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    context = SSLContext(PROTOCOL_SSLv23)

    # SSLv2 considered harmful.
    context.options |= OP_NO_SSLv2

    # SSLv3 has problematic security and is only required for really old
    # clients such as IE6 on Windows XP
    context.options |= OP_NO_SSLv3

    # disable compression to prevent CRIME attacks (OpenSSL 1.0+)
    context.options |= getattr(_ssl, "OP_NO_COMPRESSION", 0)

    if purpose == Purpose.SERVER_AUTH:
        # verify certs and host name in client mode
        context.verify_mode = CERT_REQUIRED
        context.check_hostname = True
    elif purpose == Purpose.CLIENT_AUTH:
        # Prefer the server's ciphers by default so that we get stronger
        # encryption
        context.options |= getattr(_ssl, "OP_CIPHER_SERVER_PREFERENCE", 0)

        # Use single use keys in order to improve forward secrecy
        context.options |= getattr(_ssl, "OP_SINGLE_DH_USE", 0)
        context.options |= getattr(_ssl, "OP_SINGLE_ECDH_USE", 0)

        # disallow ciphers with known vulnerabilities
        context.set_ciphers(_RESTRICTED_SERVER_CIPHERS)

    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        # no explicit cafile, capath or cadata but the verify mode is
        # CERT_OPTIONAL or CERT_REQUIRED. Let's try to load default system
        # root CA certificates for the given purpose. This may fail silently.
        context.load_default_certs(purpose)
    return context

def _create_unverified_context(protocol=PROTOCOL_SSLv23, cert_reqs=None,
                           check_hostname=False, purpose=Purpose.SERVER_AUTH,
                           certfile=None, keyfile=None,
                           cafile=None, capath=None, cadata=None):
    """Create a SSLContext object for Python stdlib modules

    All Python stdlib modules shall use this function to create SSLContext
    objects in order to keep common settings in one place. The configuration
    is less restrict than create_default_context()'s to increase backward
    compatibility.
    """
    if not isinstance(purpose, _ASN1Object):
        raise TypeError(purpose)

    context = SSLContext(protocol)
    # SSLv2 considered harmful.
    context.options |= OP_NO_SSLv2
    # SSLv3 has problematic security and is only required for really old
    # clients such as IE6 on Windows XP
    context.options |= OP_NO_SSLv3

    if cert_reqs is not None:
        context.verify_mode = cert_reqs
    context.check_hostname = check_hostname

    if keyfile and not certfile:
        raise ValueError("certfile must be specified")
    if certfile or keyfile:
        context.load_cert_chain(certfile, keyfile)

    # load CA root certs
    if cafile or capath or cadata:
        context.load_verify_locations(cafile, capath, cadata)
    elif context.verify_mode != CERT_NONE:
        # no explicit cafile, capath or cadata but the verify mode is
        # CERT_OPTIONAL or CERT_REQUIRED. Let's try to load default system
        # root CA certificates for the given purpose. This may fail silently.
        context.load_default_certs(purpose)

    return context

# Used by http.client if no context is explicitly passed.
_create_default_https_context = create_default_context


# Backwards compatibility alias, even though it's not a public name.
_create_stdlib_context = _create_unverified_context


class SSLSocket(socket):

    def __init__(self, sock=None, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=CERT_NONE,
                 ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None,
                 suppress_ragged_eofs=True, npn_protocols=None, ciphers=None,
                 server_hostname=None,
                 _context=None):

        self._makefile_refs = 0
        if _context:
            self._context = _context
        else:
            if server_side and not certfile:
                raise ValueError("certfile must be specified for server-side "
                                 "operations")
            if keyfile and not certfile:
                raise ValueError("certfile must be specified")
            if certfile and not keyfile:
                keyfile = certfile
            self._context = SSLContext(ssl_version)
            self._context.verify_mode = cert_reqs
            if ca_certs:
                self._context.load_verify_locations(ca_certs)
            if certfile:
                self._context.load_cert_chain(certfile, keyfile)
            if npn_protocols:
                self._context.set_npn_protocols(npn_protocols)
            if ciphers:
                self._context.set_ciphers(ciphers)
            self.keyfile = keyfile
            self.certfile = certfile
            self.cert_reqs = cert_reqs
            self.ssl_version = ssl_version
            self.ca_certs = ca_certs
            self.ciphers = ciphers
        # Can't use sock.type as other flags (such as SOCK_NONBLOCK) get
        # mixed in.
        if sock.getsockopt(SOL_SOCKET, SO_TYPE) != SOCK_STREAM:
            raise NotImplementedError("only stream sockets are supported")
        socket.__init__(self, _sock=sock._sock)
        # The initializer for socket overrides the methods send(), recv(), etc.
        # in the instancce, which we don't need -- but we want to provide the
        # methods defined in SSLSocket.
        for attr in _delegate_methods:
            try:
                delattr(self, attr)
            except AttributeError:
                pass
        if server_side and server_hostname:
            raise ValueError("server_hostname can only be specified "
                             "in client mode")
        if self._context.check_hostname and not server_hostname:
            raise ValueError("check_hostname requires server_hostname")
        self.server_side = server_side
        self.server_hostname = server_hostname
        self.do_handshake_on_connect = do_handshake_on_connect
        self.suppress_ragged_eofs = suppress_ragged_eofs
        self.settimeout(sock.gettimeout())

        # See if we are connected
        try:
            self.getpeername()
        except socket_error as e:
            if e.errno != errno.ENOTCONN:
                raise
            connected = False
        else:
            connected = True

        self._closed = False
        self._sslobj = None
        self._connected = connected
        if connected:
            # create the SSL object
            try:
                self._sslobj = self._context._wrap_socket(self._sock, server_side,
                                                          server_hostname, ssl_sock=self)
                if do_handshake_on_connect:
                    timeout = self.gettimeout()
                    if timeout == 0.0:
                        # non-blocking
                        raise ValueError("do_handshake_on_connect should not be specified for non-blocking sockets")
                    self.do_handshake()

            except socket_error as x:
                self.close()
                raise x

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, ctx):
        self._context = ctx
        self._sslobj.context = ctx

    def dup(self):
        raise NotImplemented("Can't dup() %s instances" %
                             self.__class__.__name__)

    def _checkClosed(self, msg=None):
        # raise an exception here if you wish to check for spurious closes
        pass

    def _check_connected(self):
        if not self._connected:
            # getpeername() will raise ENOTCONN if the socket is really
            # not connected; note that we can be connected even without
            # _connected being set, e.g. if connect() first returned
            # EAGAIN.
            self.getpeername()

    def read(self, len=0, buffer=None):
        """Read up to LEN bytes and return them.
        Return zero-length string on EOF."""
        while True:
            try:
                if buffer is not None:
                    return self._sslobj.read(len, buffer)
                else:
                    return self._sslobj.read(len or 1024)
            except SSLWantReadError:
                if self.timeout == 0.0:
                    raise
                self._wait(self._read_event, timeout_exc=_SSLErrorReadTimeout)
            except SSLWantWriteError:
                if self.timeout == 0.0:
                    raise
                # note: using _SSLErrorReadTimeout rather than _SSLErrorWriteTimeout below is intentional
                self._wait(self._write_event, timeout_exc=_SSLErrorReadTimeout)
            except SSLError as ex:
                if ex.args[0] == SSL_ERROR_EOF and self.suppress_ragged_eofs:
                    if buffer is not None:
                        return 0
                    else:
                        return b''
                else:
                    raise

    def write(self, data):
        """Write DATA to the underlying SSL channel.  Returns
        number of bytes of DATA actually transmitted."""
        while True:
            try:
                return self._sslobj.write(data)
            except SSLError as ex:
                if ex.args[0] == SSL_ERROR_WANT_READ:
                    if self.timeout == 0.0:
                        raise
                    self._wait(self._read_event, timeout_exc=_SSLErrorWriteTimeout)
                elif ex.args[0] == SSL_ERROR_WANT_WRITE:
                    if self.timeout == 0.0:
                        raise
                    self._wait(self._write_event, timeout_exc=_SSLErrorWriteTimeout)
                else:
                    raise

    def getpeercert(self, binary_form=False):
        """Returns a formatted version of the data in the
        certificate provided by the other end of the SSL channel.
        Return None if no certificate was provided, {} if a
        certificate was provided, but not validated."""

        self._checkClosed()
        self._check_connected()
        return self._sslobj.peer_certificate(binary_form)

    def selected_npn_protocol(self):
        self._checkClosed()
        if not self._sslobj or not _ssl.HAS_NPN:
            return None
        else:
            return self._sslobj.selected_npn_protocol()

    def cipher(self):
        self._checkClosed()
        if not self._sslobj:
            return None
        else:
            return self._sslobj.cipher()

    def compression(self):
        self._checkClosed()
        if not self._sslobj:
            return None
        else:
            return self._sslobj.compression()

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
                    return self._sslobj.write(data)
                except SSLWantReadError:
                    if self.timeout == 0.0:
                        return 0
                    self._wait(self._read_event)
                except SSLWantWriteError:
                    if self.timeout == 0.0:
                        return 0
                    self._wait(self._write_event)
        else:
            return socket.send(self, data, flags, timeout)

    def sendto(self, data, flags_or_addr, addr=None):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("sendto not allowed on instances of %s" %
                             self.__class__)
        elif addr is None:
            return socket.sendto(self, data, flags_or_addr)
        else:
            return socket.sendto(self, data, flags_or_addr, addr)

    def sendmsg(self, *args, **kwargs):
        # Ensure programs don't send data unencrypted if they try to
        # use this method.
        raise NotImplementedError("sendmsg not allowed on instances of %s" %
                                  self.__class__)

    def sendall(self, data, flags=0):
        self._checkClosed()
        if self._sslobj:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to sendall() on %s" %
                    self.__class__)
            amount = len(data)
            count = 0
            while (count < amount):
                v = self.send(data[count:])
                count += v
            return amount
        else:
            return socket.sendall(self, data, flags)

    def recv(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to recv() on %s" %
                    self.__class__)
            return self.read(buflen)
        else:
            return socket.recv(self, buflen, flags)

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
            return self.read(nbytes, buffer)
        else:
            return socket.recv_into(self, buffer, nbytes, flags)

    def recvfrom(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("recvfrom not allowed on instances of %s" %
                             self.__class__)
        else:
            return socket.recvfrom(self, buflen, flags)

    def recvfrom_into(self, buffer, nbytes=None, flags=0):
        self._checkClosed()
        if self._sslobj:
            raise ValueError("recvfrom_into not allowed on instances of %s" %
                             self.__class__)
        else:
            return socket.recvfrom_into(self, buffer, nbytes, flags)

    def recvmsg(self, *args, **kwargs):
        raise NotImplementedError("recvmsg not allowed on instances of %s" %
                                  self.__class__)

    def recvmsg_into(self, *args, **kwargs):
        raise NotImplementedError("recvmsg_into not allowed on instances of "
                                  "%s" % self.__class__)

    def pending(self):
        self._checkClosed()
        if self._sslobj:
            return self._sslobj.pending()
        else:
            return 0

    def shutdown(self, how):
        self._checkClosed()
        self._sslobj = None
        socket.shutdown(self, how)

    def close(self):
        if self._makefile_refs < 1:
            self._sslobj = None
            socket.close(self)
        else:
            self._makefile_refs -= 1

    def unwrap(self):
        if self._sslobj:
            s = self._sslobj.shutdown()
            self._sslobj = None
            return s
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def _real_close(self):
        self._sslobj = None
        socket._real_close(self)

    def do_handshake(self):
        """Perform a TLS/SSL handshake."""
        while True:
            try:
                return self._sslobj.do_handshake()
            except SSLWantReadError:
                if self.timeout == 0.0:
                    raise
                self._wait(self._read_event, timeout_exc=_SSLErrorHandshakeTimeout)
            except SSLWantWriteError:
                if self.timeout == 0.0:
                    raise
                self._wait(self._write_event, timeout_exc=_SSLErrorHandshakeTimeout)

        if self.context.check_hostname:
            if not self.server_hostname:
                raise ValueError("check_hostname needs server_hostname "
                                 "argument")
            match_hostname(self.getpeercert(), self.server_hostname)

    def _real_connect(self, addr, connect_ex):
        if self.server_side:
            raise ValueError("can't connect in server-side mode")
        # Here we assume that the socket is client-side, and not
        # connected at the time of the call.  We connect it, then wrap it.
        if self._connected:
            raise ValueError("attempt to connect already-connected SSLSocket!")
        self._sslobj = self.context._wrap_socket(self._sock, False, self.server_hostname, ssl_sock=self)
        try:
            if connect_ex:
                rc = socket.connect_ex(self, addr)
            else:
                rc = None
                socket.connect(self, addr)
            if not rc:
                self._connected = True
                if self.do_handshake_on_connect:
                    self.do_handshake()
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
        newsock = self.context.wrap_socket(newsock,
                    do_handshake_on_connect=self.do_handshake_on_connect,
                    suppress_ragged_eofs=self.suppress_ragged_eofs,
                    server_side=True)
        return newsock, addr

    def makefile(self, mode='r', bufsize=-1):

        """Make and return a file-like object that
        works with the SSL connection.  Just use the code
        from the socket module."""

        self._makefile_refs += 1
        # close=True so as to decrement the reference count when done with
        # the file-like object.
        return _fileobject(self, mode, bufsize, close=True)

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

    def version(self):
        """
        Return a string identifying the protocol version used by the
        current SSL channel, or None if there is no established channel.
        """
        if self._sslobj is None:
            return None
        return self._sslobj.version()


_SSLErrorReadTimeout = SSLError('The read operation timed out')
_SSLErrorWriteTimeout = SSLError('The write operation timed out')
_SSLErrorHandshakeTimeout = SSLError('The handshake operation timed out')

def wrap_socket(sock, keyfile=None, certfile=None,
                server_side=False, cert_reqs=CERT_NONE,
                ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                do_handshake_on_connect=True,
                suppress_ragged_eofs=True,
                ciphers=None):

    return SSLSocket(sock=sock, keyfile=keyfile, certfile=certfile,
                     server_side=server_side, cert_reqs=cert_reqs,
                     ssl_version=ssl_version, ca_certs=ca_certs,
                     do_handshake_on_connect=do_handshake_on_connect,
                     suppress_ragged_eofs=suppress_ragged_eofs,
                     ciphers=ciphers)

def get_server_certificate(addr, ssl_version=PROTOCOL_SSLv23, ca_certs=None):
    """Retrieve the certificate from the server at the specified address,
    and return it as a PEM-encoded string.
    If 'ca_certs' is specified, validate the server cert against it.
    If 'ssl_version' is specified, use it in the connection attempt."""

    host, port = addr
    if ca_certs is not None:
        cert_reqs = CERT_REQUIRED
    else:
        cert_reqs = CERT_NONE
    context = _create_stdlib_context(ssl_version,
                                     cert_reqs=cert_reqs,
                                     cafile=ca_certs)
    with closing(create_connection(addr)) as sock:
        with closing(context.wrap_socket(sock)) as sslsock:
            dercert = sslsock.getpeercert(True)
    return DER_cert_to_PEM_cert(dercert)
