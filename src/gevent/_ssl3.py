# Wrapper module for _ssl. Written by Bill Janssen.
# Ported to gevent by Denis Bilenko.
"""SSL wrapper for socket objects on Python 3.

For the documentation, refer to :mod:`ssl` module manual.

This module implements cooperative SSL socket wrappers.
"""
# Our import magic sadly makes this warning useless
# pylint: disable=undefined-variable

from __future__ import absolute_import
import ssl as __ssl__

_ssl = __ssl__._ssl # pylint:disable=no-member

import errno
from gevent.socket import socket, timeout_default
from gevent.socket import error as socket_error
from gevent.socket import timeout as _socket_timeout
from gevent._util import copy_globals

from weakref import ref as _wref

__implements__ = [
    'SSLContext',
    'SSLSocket',
    'wrap_socket',
    'get_server_certificate',
]

# Import all symbols from Python's ssl.py, except those that we are implementing
# and "private" symbols.
__imports__ = copy_globals(__ssl__, globals(),
                           # SSLSocket *must* subclass gevent.socket.socket; see issue 597
                           names_to_ignore=__implements__ + ['socket'],
                           dunder_names_to_keep=())

__all__ = __implements__ + __imports__
if 'namedtuple' in __all__:
    __all__.remove('namedtuple')

orig_SSLContext = __ssl__.SSLContext # pylint:disable=no-member


class SSLContext(orig_SSLContext):
    def wrap_socket(self, sock, server_side=False,
                    do_handshake_on_connect=True,
                    suppress_ragged_eofs=True,
                    server_hostname=None,
                    session=None): # 3.6
        # Sadly, using *args and **kwargs doesn't work
        return SSLSocket(sock=sock, server_side=server_side,
                         do_handshake_on_connect=do_handshake_on_connect,
                         suppress_ragged_eofs=suppress_ragged_eofs,
                         server_hostname=server_hostname,
                         _context=self,
                         _session=session)

    if not hasattr(orig_SSLContext, 'check_hostname'):
        # Python 3.3 lacks this
        check_hostname = False

    if hasattr(orig_SSLContext.options, 'setter'):
        # In 3.6, these became properties. They want to access the
        # property __set__ method in the superclass, and they do so by using
        # super(SSLContext, SSLContext). But we rebind SSLContext when we monkey
        # patch, which causes infinite recursion.
        # https://github.com/python/cpython/commit/328067c468f82e4ec1b5c510a4e84509e010f296
        @orig_SSLContext.options.setter
        def options(self, value):
            super(orig_SSLContext, orig_SSLContext).options.__set__(self, value)

        @orig_SSLContext.verify_flags.setter
        def verify_flags(self, value):
            super(orig_SSLContext, orig_SSLContext).verify_flags.__set__(self, value)

        @orig_SSLContext.verify_mode.setter
        def verify_mode(self, value):
            super(orig_SSLContext, orig_SSLContext).verify_mode.__set__(self, value)


class _contextawaresock(socket._gevent_sock_class): # Python 2: pylint:disable=slots-on-old-class
    # We have to pass the raw stdlib socket to SSLContext.wrap_socket.
    # That method in turn can pass that object on to things like SNI callbacks.
    # It wouldn't have access to any of the attributes on the SSLSocket, like
    # context, that it's supposed to (see test_ssl.test_sni_callback). Our
    # solution is to keep a weak reference to the SSLSocket on the raw
    # socket and delegate.

    # We keep it in a slot to avoid having the ability to set any attributes
    # we're not prepared for (because we don't know what to delegate.)

    __slots__ = ('_sslsock',)

    @property
    def context(self):
        return self._sslsock().context

    @context.setter
    def context(self, ctx):
        self._sslsock().context = ctx

    @property
    def session(self):
        """The SSLSession for client socket."""
        return self._sslsock().session

    @session.setter
    def session(self, session):
        self._sslsock().session = session

    def __getattr__(self, name):
        try:
            return getattr(self._sslsock(), name)
        except RuntimeError:
            # XXX: If the attribute doesn't exist,
            # we infinitely recurse
            pass
        raise AttributeError(name)


class SSLSocket(socket):
    """
    gevent `ssl.SSLSocket <https://docs.python.org/3/library/ssl.html#ssl-sockets>`_
    for Python 3.
    """

    # pylint:disable=too-many-instance-attributes,too-many-public-methods

    _gevent_sock_class = _contextawaresock

    def __init__(self, sock=None, keyfile=None, certfile=None,
                 server_side=False, cert_reqs=CERT_NONE,
                 ssl_version=PROTOCOL_SSLv23, ca_certs=None,
                 do_handshake_on_connect=True,
                 family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None,
                 suppress_ragged_eofs=True, npn_protocols=None, ciphers=None,
                 server_hostname=None,
                 _session=None, # 3.6
                 _context=None):
        # pylint:disable=too-many-locals,too-many-statements,too-many-branches
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
        if server_side:
            if server_hostname:
                raise ValueError("server_hostname can only be specified "
                                 "in client mode")
            if _session is not None:
                raise ValueError("session can only be specified "
                                 "in client mode")
        if self._context.check_hostname and not server_hostname:
            raise ValueError("check_hostname requires server_hostname")
        self._session = _session
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

        self._sock._sslsock = _wref(self)
        self._closed = False
        self._sslobj = None
        self._connected = connected
        if connected:
            # create the SSL object
            try:
                self._sslobj = self._context._wrap_socket(self._sock, server_side,
                                                          server_hostname)
                if _session is not None: # 3.6
                    self._sslobj = SSLObject(self._sslobj, owner=self, session=self._session)
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

    @property
    def session(self):
        """The SSLSession for client socket."""
        if self._sslobj is not None:
            return self._sslobj.session

    @session.setter
    def session(self, session):
        self._session = session
        if self._sslobj is not None:
            self._sslobj.session = session

    @property
    def session_reused(self):
        """Was the client session reused during handshake"""
        if self._sslobj is not None:
            return self._sslobj.session_reused

    def dup(self):
        raise NotImplementedError("Can't dup() %s instances" %
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

    def read(self, len=1024, buffer=None):
        """Read up to LEN bytes and return them.
        Return zero-length string on EOF."""
        # pylint:disable=too-many-branches
        self._checkClosed()

        while True:
            if not self._sslobj:
                raise ValueError("Read on closed or unwrapped SSL socket.")
            if len == 0:
                return b'' if buffer is None else 0
            # Negative lengths are handled natively when the buffer is None
            # to raise a ValueError
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
                        return b''
                    else:
                        return 0
                else:
                    raise

    def write(self, data):
        """Write DATA to the underlying SSL channel.  Returns
        number of bytes of DATA actually transmitted."""
        self._checkClosed()

        while True:
            if not self._sslobj:
                raise ValueError("Write on closed or unwrapped SSL socket.")

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
        try:
            c = self._sslobj.peer_certificate
        except AttributeError:
            # 3.6
            c = self._sslobj.getpeercert

        return c(binary_form)

    def selected_npn_protocol(self):
        self._checkClosed()
        if not self._sslobj or not _ssl.HAS_NPN:
            return None
        else:
            return self._sslobj.selected_npn_protocol()

    if hasattr(_ssl, 'HAS_ALPN'):
        # 3.5+
        def selected_alpn_protocol(self):
            self._checkClosed()
            if not self._sslobj or not _ssl.HAS_ALPN: # pylint:disable=no-member
                return None
            else:
                return self._sslobj.selected_alpn_protocol()

        def shared_ciphers(self):
            """Return a list of ciphers shared by the client during the handshake or
            None if this is not a valid server connection.
            """
            return self._sslobj.shared_ciphers()

        def version(self):
            """Return a string identifying the protocol version used by the
            current SSL channel. """
            if not self._sslobj:
                return None
            return self._sslobj.version()

        # We inherit sendfile from super(); it always uses `send`

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

        try:
            return socket.sendall(self, data, flags)
        except _socket_timeout:
            if self.timeout == 0.0:
                # Raised by the stdlib on non-blocking sockets
                raise SSLWantWriteError("The operation did not complete (write)")
            raise

    def recv(self, buflen=1024, flags=0):
        self._checkClosed()
        if self._sslobj:
            if flags != 0:
                raise ValueError(
                    "non-zero flags not allowed in calls to recv() on %s" %
                    self.__class__)
            if buflen == 0:
                # https://github.com/python/cpython/commit/00915577dd84ba75016400793bf547666e6b29b5
                # Python #23804
                return b''
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
            while True:
                try:
                    s = self._sslobj.shutdown()
                    break
                except SSLWantReadError:
                    if self.timeout == 0.0:
                        return 0
                    self._wait(self._read_event)
                except SSLWantWriteError:
                    if self.timeout == 0.0:
                        return 0
                    self._wait(self._write_event)

            self._sslobj = None
            # The return value of shutting down the SSLObject is the
            # original wrapped socket, i.e., _contextawaresock. But that
            # object doesn't have the gevent wrapper around it so it can't
            # be used. We have to wrap it back up with a gevent wrapper.
            sock = socket(family=s.family, type=s.type, proto=s.proto, fileno=s.fileno())
            s.detach()
            return sock
        else:
            raise ValueError("No SSL wrapper around " + str(self))

    def _real_close(self):
        self._sslobj = None
        # self._closed = True
        socket._real_close(self)

    def do_handshake(self):
        """Perform a TLS/SSL handshake."""
        self._check_connected()
        while True:
            try:
                self._sslobj.do_handshake()
                break
            except SSLWantReadError:
                if self.timeout == 0.0:
                    raise
                self._wait(self._read_event, timeout_exc=_SSLErrorHandshakeTimeout)
            except SSLWantWriteError:
                if self.timeout == 0.0:
                    raise
                self._wait(self._write_event, timeout_exc=_SSLErrorHandshakeTimeout)

        if self._context.check_hostname:
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
        self._sslobj = self._context._wrap_socket(self._sock, False, self.server_hostname)
        if self._session is not None: # 3.6
            self._sslobj = SSLObject(self._sslobj, owner=self, session=self._session)
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
        newsock = self._context.wrap_socket(newsock,
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


# Python 3.2 onwards raise normal timeout errors, not SSLError.
# See https://bugs.python.org/issue10272
_SSLErrorReadTimeout = _socket_timeout('The read operation timed out')
_SSLErrorWriteTimeout = _socket_timeout('The write operation timed out')
_SSLErrorHandshakeTimeout = _socket_timeout('The handshake operation timed out')


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

    _, _ = addr
    if ca_certs is not None:
        cert_reqs = CERT_REQUIRED
    else:
        cert_reqs = CERT_NONE
    s = create_connection(addr)
    s = wrap_socket(s, ssl_version=ssl_version,
                    cert_reqs=cert_reqs, ca_certs=ca_certs)
    dercert = s.getpeercert(True)
    s.close()
    return DER_cert_to_PEM_cert(dercert)
