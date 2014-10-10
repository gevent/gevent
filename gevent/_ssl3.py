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


class SSLSocket(socket):

    def __init__(self, sock=None, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=CERT_NONE,
                 ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None,
                 suppress_ragged_eofs=True, npn_protocols=None, ciphers=None,
                 server_hostname=None,
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
        # Can't use sock.type as other flags (such as SOCK_NONBLOCK) get
        # mixed in.
        if sock.getsockopt(SOL_SOCKET, SO_TYPE) != SOCK_STREAM:
            raise NotImplementedError("only stream sockets are supported")
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

    def _checkClosed(self, msg=None):
        # raise an exception here if you wish to check for spurious closes
        pass

    def read(self, len=1024, buffer=None):
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
                    if buffer is None:
                        return ''
                    else:
                        return 0
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
                raise ValueError("non-zero flags not allowed in calls to recv_into() on %s" % self.__class__)
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

    def unwrap(self):
        if self._sslobj:
            s = self._sslobj.shutdown()
            self._sslobj = None
            return s
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def _real_close(self):
        self._sslobj = None
        # self._closed = True
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
        newsock = self.context.wrap_socket(newsock,
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
            raise NotImplementedError("{0} channel binding type not implemented".format(cb_type))
        if self._sslobj is None:
            return None
        return self._sslobj.tls_unique_cb()


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
    s = create_connection(addr)
    s = wrap_socket(s, ssl_version=ssl_version,
                    cert_reqs=cert_reqs, ca_certs=ca_certs)
    dercert = s.getpeercert(True)
    s.close()
    return DER_cert_to_PEM_cert(dercert)
