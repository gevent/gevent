# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.
from __future__ import absolute_import

# standard functions and classes that this module re-implements in a gevent-aware way:
_implements = ['create_connection',
               'socket',
               'SocketType',
               'fromfd',
               'socketpair']

__dns__ = ['getaddrinfo',
           'gethostbyname',
           'gethostbyname_ex',
           'gethostbyaddr',
           'getnameinfo',
           'getfqdn']

_implements += __dns__

# non-standard functions that this module provides:
__extensions__ = ['wait_read',
                  'wait_write',
                  'wait_readwrite']

# standard functions and classes that this module re-imports
__imports__ = ['error',
               'gaierror',
               'herror',
               'htonl',
               'htons',
               'ntohl',
               'ntohs',
               'inet_aton',
               'inet_ntoa',
               'inet_pton',
               'inet_ntop',
               'timeout',
               'gethostname',
               'getprotobyname',
               'getservbyname',
               'getservbyport',
               'getdefaulttimeout',
               'setdefaulttimeout',
               # Windows:
               'errorTab',
               # Python 3
               'AddressFamily',
               'SocketKind',
               'CMSG_LEN',
               'CMSG_SPACE',
               'dup',
               'if_indextoname',
               'if_nameindex',
               'if_nametoindex',
               'sethostname']


import sys
from gevent.hub import get_hub, string_types, integer_types
from gevent.timeout import Timeout

is_windows = sys.platform == 'win32'

if is_windows:
    # no such thing as WSAEPERM or error code 10001 according to winsock.h or MSDN
    from errno import WSAEINVAL as EINVAL
    from errno import WSAEWOULDBLOCK as EWOULDBLOCK
    from errno import WSAEINPROGRESS as EINPROGRESS
    from errno import WSAEALREADY as EALREADY
    from errno import WSAEISCONN as EISCONN
    from gevent.win32util import formatError as strerror
    EAGAIN = EWOULDBLOCK
else:
    from errno import EINVAL
    from errno import EWOULDBLOCK
    from errno import EINPROGRESS
    from errno import EALREADY
    from errno import EAGAIN
    from errno import EISCONN
    from os import strerror

try:
    from errno import EBADF
except ImportError:
    EBADF = 9

import _socket
_realsocket = _socket.socket
import socket as __socket__


for name in __imports__[:]:
    try:
        value = getattr(__socket__, name)
        globals()[name] = value
    except AttributeError:
        __imports__.remove(name)

for name in __socket__.__all__:
    value = getattr(__socket__, name)
    if isinstance(value, integer_types) or isinstance(value, string_types):
        globals()[name] = value
        __imports__.append(name)

del name, value


def wait(io, timeout=None, timeout_exc=timeout('timed out')):
    """Block the current greenlet until *io* is ready.

    If *timeout* is non-negative, then *timeout_exc* is raised after *timeout* second has passed.
    By default *timeout_exc* is ``socket.timeout('timed out')``.

    If :func:`cancel_wait` is called, raise ``socket.error(EBADF, 'File descriptor was closed in another greenlet')``.
    """
    assert io.callback is None, 'This socket is already used by another greenlet: %r' % (io.callback, )
    if timeout is not None:
        timeout = Timeout.start_new(timeout, timeout_exc)
    try:
        return get_hub().wait(io)
    finally:
        if timeout is not None:
            timeout.cancel()
    # rename "io" to "watcher" because wait() works with any watcher


def wait_read(fileno, timeout=None, timeout_exc=timeout('timed out')):
    """Block the current greenlet until *fileno* is ready to read.

    If *timeout* is non-negative, then *timeout_exc* is raised after *timeout* second has passed.
    By default *timeout_exc* is ``socket.timeout('timed out')``.

    If :func:`cancel_wait` is called, raise ``socket.error(EBADF, 'File descriptor was closed in another greenlet')``.
    """
    io = get_hub().loop.io(fileno, 1)
    return wait(io, timeout, timeout_exc)


def wait_write(fileno, timeout=None, timeout_exc=timeout('timed out'), event=None):
    """Block the current greenlet until *fileno* is ready to write.

    If *timeout* is non-negative, then *timeout_exc* is raised after *timeout* second has passed.
    By default *timeout_exc* is ``socket.timeout('timed out')``.

    If :func:`cancel_wait` is called, raise ``socket.error(EBADF, 'File descriptor was closed in another greenlet')``.
    """
    io = get_hub().loop.io(fileno, 2)
    return wait(io, timeout, timeout_exc)


def wait_readwrite(fileno, timeout=None, timeout_exc=timeout('timed out'), event=None):
    """Block the current greenlet until *fileno* is ready to read or write.

    If *timeout* is non-negative, then *timeout_exc* is raised after *timeout* second has passed.
    By default *timeout_exc* is ``socket.timeout('timed out')``.

    If :func:`cancel_wait` is called, raise ``socket.error(EBADF, 'File descriptor was closed in another greenlet')``.
    """
    io = get_hub().loop.io(fileno, 3)
    return wait(io, timeout, timeout_exc)


cancel_wait_ex = error(EBADF, 'File descriptor was closed in another greenlet')


def cancel_wait(watcher):
    get_hub().cancel_wait(watcher, cancel_wait_ex)


class BlockingResolver(object):

    def __init__(self, hub=None):
        pass

    def close(self):
        pass

    for method in ['gethostbyname',
                   'gethostbyname_ex',
                   'getaddrinfo',
                   'gethostbyaddr',
                   'getnameinfo']:
        locals()[method] = staticmethod(getattr(_socket, method))


def gethostbyname(hostname):
    return get_hub().resolver.gethostbyname(hostname)


def gethostbyname_ex(hostname):
    return get_hub().resolver.gethostbyname_ex(hostname)


def getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    return get_hub().resolver.getaddrinfo(host, port, family, socktype, proto, flags)


def gethostbyaddr(ip_address):
    return get_hub().resolver.gethostbyaddr(ip_address)


def getnameinfo(sockaddr, flags):
    return get_hub().resolver.getnameinfo(sockaddr, flags)


def getfqdn(name=''):
    """Get fully qualified domain name from name.

    An empty argument is interpreted as meaning the local host.

    First the hostname returned by gethostbyaddr() is checked, then
    possibly existing aliases. In case no FQDN is available, hostname
    from gethostname() is returned.
    """
    name = name.strip()
    if not name or name == '0.0.0.0':
        name = gethostname()
    try:
        hostname, aliases, ipaddrs = gethostbyaddr(name)
    except error:
        pass
    else:
        aliases.insert(0, hostname)
        for name in aliases:
            if isinstance(name, bytes):
                if b'.' in name:
                    break
            elif '.' in name:
                break
        else:
            name = hostname
    return name
