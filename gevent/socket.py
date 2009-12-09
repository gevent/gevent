# Copyright (c) 2005-2006, Bob Ippolito
# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2009 Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Cooperative socket module.

This module provides socket operations and some related functions.
The API of the functions and classes matches the API of the corresponding
items in standard :mod:`socket` module exactly, but the synchronous functions
in this module only block the current greenlet and let the others run.
"""

__all__ = ['socket', 'socketpair', 'fromfd', 'gethostbyname', 'getaddrinfo', 'getnameinfo', 'wrap_ssl']

import _socket
error = _socket.error
timeout = _socket.timeout
__socket__ = __import__('socket')
_fileobject = __socket__._fileobject
try:
    sslerror = __socket__.sslerror
except AttributeError:
    pass
gaierror = __socket__.gaierror

import sys
import errno
import time
import random
import re

from gevent.hub import getcurrent, get_hub, spawn_raw, Waiter
from gevent import core

BUFFER_SIZE = 4096
_ip_re = re.compile('^[\d\.]+$')


def _wait_helper(ev, evtype):
    current, timeout_exc = ev.arg
    if evtype & core.EV_TIMEOUT:
        current.throw(timeout_exc)
    else:
        current.switch(ev)


def wait_read(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.read_event(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        switch_result = get_hub().switch()
        assert evt is switch_result, 'Invalid switch into wait_read(): %r' % (switch_result, )
    finally:
        evt.cancel()


def wait_write(fileno, timeout=-1, timeout_exc=_socket.timeout):
    evt = core.write_event(fileno, _wait_helper, timeout, (getcurrent(), timeout_exc))
    try:
        switch_result = get_hub().switch()
        assert evt is switch_result, 'Invalid switch into wait_write(): %r' % (switch_result, )
    finally:
        evt.cancel()


try:
    from OpenSSL import SSL
except ImportError:
    class SSL(object):
        class WantWriteError(object):
            pass

        class WantReadError(object):
            pass

        class ZeroReturnError(object):
            pass

        class SysCallError(object):
            pass

        class Error(object):
            pass


if sys.version_info[:2]<=(2, 4):
    # implement close argument to _fileobject that we require

    realfileobject = _fileobject

    class _fileobject(realfileobject):

        __slots__ = realfileobject.__slots__ + ['_close']

        def __init__(self, *args, **kwargs):
            self._close = kwargs.pop('close', False)
            realfileobject.__init__(self, *args, **kwargs)

        def close(self):
            try:
                if self._sock:
                    self.flush()
            finally:
                if self._close:
                    self._sock.close()
                self._sock = None


CONNECT_ERR = (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK)
CONNECT_SUCCESS = (0, errno.EISCONN)
def socket_connect(descriptor, address):
    err = descriptor.connect_ex(address)
    if err in CONNECT_ERR:
        return None
    if err not in CONNECT_SUCCESS:
        raise error(err, errno.errorcode[err])
    return descriptor


class _closedsocket(object):
    __slots__ = []
    def _dummy(*args):
        raise error(errno.EBADF, 'Bad file descriptor')
    # All _delegate_methods must also be initialized here.
    send = recv = recv_into = sendto = recvfrom = recvfrom_into = _dummy
    __getattr__ = _dummy


_delegate_methods = ("recv", "recvfrom", "recv_into", "recvfrom_into", "send", "sendto", 'sendall')

timeout_default = object()

class socket(object):
    is_secure = False # XXX remove this

    def __init__(self, family_or_realsock=_socket.AF_INET, *args, **kwargs):
        if isinstance(family_or_realsock, (int, long)):
            self.fd = _socket.socket(family_or_realsock, *args, **kwargs)
            self.timeout = _socket.getdefaulttimeout()
        else:
            if hasattr(family_or_realsock, '_sock'):
                family_or_realsock = family_or_realsock.sock
            self.fd = family_or_realsock
            self.timeout = self.fd.gettimeout()
            assert not args, args
            assert not kwargs, kwargs

        self.fd.setblocking(0)

    def __repr__(self):
        return '<%s at %s %s>' % (type(self).__name__, hex(id(self)), self._formatinfo())

    def __str__(self):
        return '<%s %s>' % (type(self).__name__, self._formatinfo())

    def _formatinfo(self):
        try:
            fileno = self.fileno()
        except Exception, ex:
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
        if self.timeout is not None:
            result += ' timeout=' + str(self.timeout)
        return result

    def __getattr__(self, item):
        return getattr(self.fd, item)

    def accept(self):
        if self.timeout==0.0:
            return self.fd.accept()
        fd = self.fd
        while True:
            try:
                res = self.fd.accept()
            except error, e:
                if e[0] == errno.EWOULDBLOCK:
                    res = None
                else:
                    raise
            if res is not None:
                client, addr = res
                return type(self)(client), addr
            wait_read(fd.fileno(), timeout=self.timeout, timeout_exc=timeout)

    def close(self):
        self.fd = _closedsocket()
        dummy = self.fd._dummy
        for method in _delegate_methods:
            setattr(self, method, dummy)

    def connect(self, address):
        if isinstance(address, tuple) and len(address)==2:
            address = gethostbyname(address[0]), address[1]
        if self.timeout==0.0:
            return self.fd.connect(address)
        fd = self.fd
        if self.timeout is None:
            while not socket_connect(fd, address):
                wait_write(fd.fileno(), timeout_exc=timeout)
        else:
            end = time.time() + self.timeout
            while True:
                if socket_connect(fd, address):
                    return
                if time.time() >= end:
                    raise timeout
                wait_write(fd.fileno(), timeout=end-time.time(), timeout_exc=timeout)

    def connect_ex(self, address):
        if self.timeout==0.0:
            return self.fd.connect_ex(address)
        fd = self.fd
        if self.timeout is None:
            while not socket_connect(fd, address):
                try:
                    wait_write(fd.fileno(), timeout_exc=timeout)
                except error, ex:
                    return ex[0]
        else:
            end = time.time() + self.timeout
            while True:
                if socket_connect(fd, address):
                    return 0
                if time.time() >= end:
                    raise timeout
                try:
                    wait_write(fd.fileno(), timeout=end-time.time(), timeout_exc=timeout)
                except error, ex:
                    return ex[0]

    def dup(self, *args, **kw):
        sock = self.fd.dup(*args, **kw)
        newsock = type(self)(sock)
        newsock.settimeout(self.timeout)
        return newsock

    def makefile(self, mode='r', bufsize=-1):
        return _fileobject(self.dup(), mode, bufsize)

    def recv(self, *args):
        if self.timeout!=0.0:
            wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
        return self.fd.recv(*args)

    def recvfrom(self, *args):
        if self.timeout!=0.0:
            wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
        return self.fd.recvfrom(*args)

    def recvfrom_into(self, *args):
        if self.timeout!=0.0:
            wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
        return self.fd.recvfrom_into(*args)

    def recv_into(self, *args):
        if self.timeout!=0.0:
            wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
        return self.fd.recv_into(*args)

    def send(self, data, timeout=timeout_default):
        if timeout is timeout_default:
            timeout = self.timeout
        if timeout!=0.0:
            wait_write(self.fileno(), timeout=timeout, timeout_exc=_socket.timeout)
        return self.fd.send(data)

    def sendall(self, data):
        # this sendall is also reused by GreenSSL, so it must not call self.fd methods directly
        if self.timeout is None:
            data_sent = 0
            while data_sent < len(data):
                data_sent += self.send(data[data_sent:])
        elif not self.timeout:
            return self.fd.sendall(data)
        else:
            end = time.time() + self.timeout
            data_sent = 0
            while data_sent < len(data):
                left = end - time.time()
                if left <= 0:
                    raise timeout
                data_sent += self.send(data[data_sent:], timeout=left)

    def sendto(self, *args):
        if self.timeout!=0.0:
            wait_write(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
        return self.fd.sendto(*args)

    def setblocking(self, flag):
        if flag:
            self.timeout = None
        else:
            self.timeout = 0.0

    def settimeout(self, howlong):
        if howlong is None:
            self.setblocking(True)
            return
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

GreenSocket = socket # XXX this alias will be removed

SysCallError_code_mapping = {-1: 8}


class GreenSSL(socket):
    is_secure = True

    def __init__(self, fd, server_side=False):
        socket.__init__(self, fd)
        self._makefile_refs = 0
        if server_side:
            self.fd.set_accept_state()
        else:
            self.fd.set_connect_state()

    def __repr__(self):
        try:
            fileno = self.fileno()
        except Exception, ex:
            fileno = str(ex)
        return '<%s at %s fileno=%s timeout=%s state_string=%r>' % (type(self).__name__, hex(id(self)), fileno, self.timeout, self.fd.state_string())

    def accept(self):
        if self.timeout==0.0:
            return self.fd.accept()
        fd = self.fd
        while True:
            try:
                res = self.fd.accept()
            except error, e:
                if e[0] == errno.EWOULDBLOCK:
                    res = None
                else:
                    raise
            if res is not None:
                client, addr = res
                accepted = type(self)(client, server_side=True)
                accepted.do_handshake()
                return accepted, addr
            wait_read(fd.fileno(), timeout=self.timeout, timeout_exc=timeout)

    def do_handshake(self):
        while True:
            try:
                self.fd.do_handshake()
                break
            except SSL.WantReadError:
                wait_read(self.fileno())
            except SSL.WantWriteError:
                wait_write(self.fileno())
            except SSL.SysCallError, ex:
                raise sslerror(SysCallError_code_mapping.get(ex.args[0], ex.args[0]), ex.args[1])
            except SSL.Error, ex:
                raise sslerror(str(ex))

    def connect(self, *args):
        socket.connect(self, *args)
        self.do_handshake()

    def send(self, data, timeout=timeout_default):
        if timeout is timeout_default:
            timeout = self.timeout
        while True:
            try:
                return self.fd.send(data)
            except SSL.WantWriteError, ex:
                if self.timeout==0.0:
                    raise timeout(str(ex))
                else:
                    wait_write(self.fileno(), timeout=timeout, timeout_exc=_socket.timeout)
            except SSL.WantReadError, ex:
                if self.timeout==0.0:
                    raise timeout(str(ex))
                else:
                    wait_read(self.fileno(), timeout=timeout, timeout_exc=_socket.timeout)
            except SSL.SysCallError, e:
                if e[0] == -1 and data == "":
                    # errors when writing empty strings are expected and can be ignored
                    return 0
                raise sslerror(SysCallError_code_mapping.get(ex.args[0], ex.args[0]), ex.args[1])
            except SSL.Error, ex:
                raise sslerror(str(ex))

    def recv(self, buflen):
        pending = self.fd.pending()
        if pending:
            return self.fd.recv(min(pending, buflen))
        while True:
            try:
                return self.fd.recv(buflen)
            except SSL.WantReadError, ex:
                if self.timeout==0.0:
                    raise timeout(str(ex))
                else:
                    wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
            except SSL.WantWriteError, ex:
                if self.timeout==0.0:
                    raise timeout(str(ex))
                else:
                    wait_read(self.fileno(), timeout=self.timeout, timeout_exc=timeout)
            except SSL.ZeroReturnError:
                return ''
            except SSL.SysCallError, ex:
                raise sslerror(SysCallError_code_mapping.get(ex.args[0], ex.args[0]), ex.args[1])
            except SSL.Error, ex:
                raise sslerror(str(ex))

    def read(self, buflen=1024):
        """
        NOTE: read() in SSLObject does not have the semantics of file.read
        reading here until we have buflen bytes or hit EOF is an error
        """
        return self.recv(buflen)

    def write(self, data):
        try:
            return self.sendall(data)
        except SSL.Error, ex:
            raise sslerror(str(ex))

    def makefile(self, mode='r', bufsize=-1):
        self._makefile_refs += 1
        return _fileobject(self, mode, bufsize, close=True)

    def close (self):
        if self._makefile_refs < 1:
            self.fd.shutdown()
            # QQQ wait until shutdown completes?
        else:
            self._makefile_refs -= 1


def socketpair(*args):
    one, two = _socket.socketpair(*args)
    return socket(one), socket(two)


def fromfd(*args):
    return socket(_socket.fromfd(*args))

def socket_bind_and_listen(descriptor, addr=('', 0), backlog=50):
    set_reuse_addr(descriptor)
    descriptor.bind(addr)
    descriptor.listen(backlog)
    return descriptor

def set_reuse_addr(descriptor):
    try:
        descriptor.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, descriptor.getsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR) | 1)
    except error:
        pass

def tcp_listener(address, backlog=50):
    """
    Listen on the given (ip, port) *address* with a TCP socket.
    Returns a socket object on which one should call ``accept()`` to
    accept a connection on the newly bound socket.

    Generally, the returned socket will be passed to ``tcp_server()``,
    which accepts connections forever and spawns greenlets for
    each incoming connection.
    """
    sock = socket()
    socket_bind_and_listen(sock, address, backlog=backlog)
    return sock

def ssl_listener(address, private_key, certificate):
    """Listen on the given (ip, port) *address* with a TCP socket that
    can do SSL.

    *certificate* and *private_key* should be the filenames of the appropriate
    certificate and private key files to use with the SSL socket.

    Returns a socket object on which one should call ``accept()`` to
    accept a connection on the newly bound socket.

    Generally, the returned socket will be passed to ``tcp_server()``,
    which accepts connections forever and spawns greenlets for
    each incoming connection.
    """
    r = _socket.socket()
    sock = wrap_ssl000(r, private_key, certificate)
    socket_bind_and_listen(sock, address)
    return sock

# XXX merge this into create_connection
def connect_tcp(address, localaddr=None):
    """
    Create a TCP connection to address (host, port) and return the socket.
    Optionally, bind to localaddr (host, port) first.
    """
    desc = socket()
    if localaddr is not None:
        desc.bind(localaddr)
    desc.connect(address)
    return desc

def tcp_server(listensocket, server, *args, **kw):
    """
    Given a socket, accept connections forever, spawning greenlets
    and executing *server* for each new incoming connection.
    When *listensocket* is closed, the ``tcp_server()`` greenlet will end.

    listensocket
        The socket from which to accept connections.
    server
        The callable to call when a new connection is made.
    \*args
        The positional arguments to pass to *server*.
    \*\*kw
        The keyword arguments to pass to *server*.
    """
    try:
        try:
            while True:
                client_socket = listensocket.accept()
                spawn_raw(server, client_socket, *args, **kw)
        except error, e:
            # Broken pipe means it was shutdown
            if e[0] != 32:
                raise
    finally:
        listensocket.close()

_GLOBAL_DEFAULT_TIMEOUT = object()

def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used.
    """

    msg = "getaddrinfo returns an empty list"
    host, port = address
    for res in getaddrinfo(host, port, 0, _socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket(af, socktype, proto)
            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            sock.connect(sa)
            return sock
        except error, msg:
            if sock is not None:
                sock.close()
    raise error, msg


def create_connection_ssl(address, timeout=_GLOBAL_DEFAULT_TIMEOUT):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used.
    """

    msg = "getaddrinfo returns an empty list"
    host, port = address
    for res in getaddrinfo(host, port, 0, _socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            _sock = _socket.socket(af, socktype, proto)
            sock = wrap_ssl000(_sock)
            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            sock.connect(sa)
            return sock
        except error, msg:
            if sock is not None:
                sock.close()
    raise error, msg


# get rid of this
def wrap_ssl000(sock, keyfile=None, certfile=None):
    from OpenSSL import SSL
    context = SSL.Context(SSL.SSLv23_METHOD)
    if certfile is not None:
        context.use_certificate_file(certfile)
    if keyfile is not None:
        context.use_privatekey_file(keyfile)
    context.set_verify(SSL.VERIFY_NONE, lambda *x: True)
    timeout = sock.gettimeout()
    connection = SSL.Connection(context, sock)
    ssl_sock = GreenSSL(connection)

    try:
        sock.getpeername()
    except:
        # no, no connection yet
        pass
    else:
        # yes, do the handshake
        ssl_sock.do_handshake()

    return ssl_sock

try:
    core.dns_init()
except:
    # fallback to blocking versions
    gethostbyname = __socket__.gethostbyname
    getaddrinfo = __socket__.getaddrinfo
    getnameinfo = __socket__.getnameinfo
else:
    # NOTE:
    # use flags=core.DNS_QUERY_NO_SEARCH to avoid search, see comments in evdns.h
    # TODO:
    # might need to map evdns errors to socket errors
    # for example, DNS_ERR_NOTEXIST(3) is:
    # socket.gaierror: [Errno -2] Name or service not known

    def _dns_helper(result, type, ttl, addrs, args):
        (waiter,) = args
        waiter.switch((result, type, ttl, addrs))

    def gethostbyname(hostname):
        """gethostbyname implemented using EvDNS.

        Differs in the following ways:

        * raises gaierror with EvDNS error codes instead of standard socket error codes
        * does not support /etc/hosts (see code for hacks to make localhost work)
        * does not iterate through all addresses, instead picks a random one each time
        """
        # TODO: this is supposed to iterate through all the addresses
        # could use a global dict(hostname, iter)
        # - fix these nasty hacks for localhost, ips, etc.
        if hostname == 'localhost': # QQQ should use /etc/hosts
            return '127.0.0.1'
        if _ip_re.match(hostname):
            return hostname
        if hostname == _socket.gethostname():
            return _socket.gethostbyname(hostname)
        waiter = Waiter()
        core.dns_resolve_ipv4(hostname, 0, _dns_helper, waiter)
        result, type, ttl, addrs = waiter.wait()
        if result != core.DNS_ERR_NONE:
            raise gaierror('dns_resolve_ipv4 returned %s' % result)
        return random.choice(addrs)

    def getaddrinfo(host, port, family=__socket__.AF_UNSPEC, socktype=__socket__.SOCK_STREAM, proto=0, flags=0):
        """getaddrinfo implemented using EvDNS.

        Differs in the following ways:

        * raises gaierror with EvDNS error codes instead of standard socket error codes
        * does not support /etc/hosts
        * IPv6 support is untested.
        * AF_UNSPEC only tries IPv4
        * only supports TCP, UDP, IP protocols
        * port must be numeric, does not support string service names. see socket.getservbyname
        * only supported value for flags is core.DNS_QUERY_NO_SEARCH, see evdns.h
        """
        if _ip_re.match(host):
            return [(__socket__.AF_INET, socktype, p, '', (host, port)) for p in (6, 17, 0)]
        waiter = Waiter()
        if family == __socket__.AF_INET:
            core.dns_resolve_ipv4(host, flags, _dns_helper, waiter)
        elif family == __socket__.AF_INET6:
            core.dns_resolve_ipv6(host, flags, _dns_helper, waiter)
        elif family == __socket__.AF_UNSPEC:
            # TODO: AF_UNSPEC means try both AF_INET and AF_INET6
            family = __socket__.AF_INET
            core.dns_resolve_ipv4(host, flags, _dns_helper, waiter)
        else:
            raise NotImplementedError
        result, type, ttl, addrs = waiter.wait()
        if result != core.DNS_ERR_NONE:
            raise gaierror(result)
        r = []
        for addr in addrs:
            for p in (6, 17, 0): # tcp, udp, ip protocols
                r.append((family, socktype, p, '', (addr, port)))
        return r

    def getnameinfo(sockaddr, flags):
        """getnameinfo implemented using EvDNS.

        Differs in the following ways:

        * raises gaierror with EvDNS error codes instead of standard socket error codes
        * does not support /etc/hosts
        * IPv6 support is untested.
        * port must be numeric, does not support string service names. see socket.getservbyname
        * only supported value for flags is core.DNS_QUERY_NO_SEARCH, see evdns.h
        """

        # http://svn.python.org/view/python/trunk/Modules/socketmodule.c?view=markup
        # see socket_getnameinfo
        try:
            host, port = sockaddr[:2]
            port = int(port)
        except ValueError:
            # make testRefCountGetNameInfo pass
            del sockaddr
            raise SystemError
        waiter = Waiter()
        core.dns_resolve_reverse(host, flags, _dns_helper, waiter)
        result, type, ttl, addrs = waiter.wait()
        if result != core.DNS_ERR_NONE:
            raise gaierror(result)
        return (addrs, port)


def wrap_ssl(sock, keyfile=None, certfile=None):
    from OpenSSL import SSL
    context = SSL.Context(SSL.SSLv23_METHOD)
    if certfile is not None:
        context.use_certificate_file(certfile)
    if keyfile is not None:
        context.use_privatekey_file(keyfile)
    context.set_verify(SSL.VERIFY_NONE, lambda *x: True)
    connection = SSL.Connection(context, sock.fd)
    ssl_sock = GreenSSL(connection)
    ssl_sock.settimeout(sock.gettimeout())

    try:
        sock.getpeername()
    except:
        # no, no connection yet
        pass
    else:
        # yes, do the handshake
        ssl_sock.do_handshake()

    return ssl_sock

