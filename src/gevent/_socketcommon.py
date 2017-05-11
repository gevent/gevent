# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.
from __future__ import absolute_import

# standard functions and classes that this module re-implements in a gevent-aware way:
_implements = [
    'create_connection',
    'socket',
    'SocketType',
    'fromfd',
    'socketpair',
]

__dns__ = [
    'getaddrinfo',
    'gethostbyname',
    'gethostbyname_ex',
    'gethostbyaddr',
    'getnameinfo',
    'getfqdn',
]

_implements += __dns__

# non-standard functions that this module provides:
__extensions__ = [
    'cancel_wait',
    'wait_read',
    'wait_write',
    'wait_readwrite',
]

# standard functions and classes that this module re-imports
__imports__ = [
    'error',
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
]

__py3_imports__ = [
    # Python 3
    'AddressFamily',
    'SocketKind',
    'CMSG_LEN',
    'CMSG_SPACE',
    'dup',
    'if_indextoname',
    'if_nameindex',
    'if_nametoindex',
    'sethostname',
]

__imports__.extend(__py3_imports__)


import sys
from gevent.hub import get_hub
from gevent.hub import ConcurrentObjectUseError
from gevent.timeout import Timeout
from gevent._compat import string_types, integer_types, PY3
from gevent._util import copy_globals
from gevent._util import _NONE

is_windows = sys.platform == 'win32'
# pylint:disable=no-name-in-module,unused-import
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

_name = _value = None
__imports__ = copy_globals(__socket__, globals(),
                           only_names=__imports__,
                           ignore_missing_names=True)

for _name in __socket__.__all__:
    _value = getattr(__socket__, _name)
    if isinstance(_value, (integer_types, string_types)):
        globals()[_name] = _value
        __imports__.append(_name)

del _name, _value

_timeout_error = timeout # pylint: disable=undefined-variable


def wait(io, timeout=None, timeout_exc=_NONE):
    """
    Block the current greenlet until *io* is ready.

    If *timeout* is non-negative, then *timeout_exc* is raised after
    *timeout* second has passed. By default *timeout_exc* is
    ``socket.timeout('timed out')``.

    If :func:`cancel_wait` is called on *io* by another greenlet,
    raise an exception in this blocking greenlet
    (``socket.error(EBADF, 'File descriptor was closed in another
    greenlet')`` by default).

    :param io: A libev watcher, most commonly an IO watcher obtained from
        :meth:`gevent.core.loop.io`
    :keyword timeout_exc: The exception to raise if the timeout expires.
        By default, a :class:`socket.timeout` exception is raised.
        If you pass a value for this keyword, it is interpreted as for
        :class:`gevent.timeout.Timeout`.
    """
    if io.callback is not None:
        raise ConcurrentObjectUseError('This socket is already used by another greenlet: %r' % (io.callback, ))
    if timeout is not None:
        timeout_exc = timeout_exc if timeout_exc is not _NONE else _timeout_error('timed out')
        timeout = Timeout.start_new(timeout, timeout_exc)

    try:
        return get_hub().wait(io)
    finally:
        if timeout is not None:
            timeout.cancel()
    # rename "io" to "watcher" because wait() works with any watcher


def wait_read(fileno, timeout=None, timeout_exc=_NONE):
    """
    Block the current greenlet until *fileno* is ready to read.

    For the meaning of the other parameters and possible exceptions,
    see :func:`wait`.

    .. seealso:: :func:`cancel_wait`
     """
    io = get_hub().loop.io(fileno, 1)
    return wait(io, timeout, timeout_exc)


def wait_write(fileno, timeout=None, timeout_exc=_NONE, event=_NONE):
    """
    Block the current greenlet until *fileno* is ready to write.

    For the meaning of the other parameters and possible exceptions,
    see :func:`wait`.

    :keyword event: Ignored. Applications should not pass this parameter.
       In the future, it may become an error.

    .. seealso:: :func:`cancel_wait`
    """
    # pylint:disable=unused-argument
    io = get_hub().loop.io(fileno, 2)
    return wait(io, timeout, timeout_exc)


def wait_readwrite(fileno, timeout=None, timeout_exc=_NONE, event=_NONE):
    """
    Block the current greenlet until *fileno* is ready to read or
    write.

    For the meaning of the other parameters and possible exceptions,
    see :func:`wait`.

    :keyword event: Ignored. Applications should not pass this parameter.
       In the future, it may become an error.

    .. seealso:: :func:`cancel_wait`
    """
    # pylint:disable=unused-argument
    io = get_hub().loop.io(fileno, 3)
    return wait(io, timeout, timeout_exc)

#: The exception raised by default on a call to :func:`cancel_wait`
class cancel_wait_ex(error): # pylint: disable=undefined-variable
    def __init__(self):
        super(cancel_wait_ex, self).__init__(
            EBADF,
            'File descriptor was closed in another greenlet')


def cancel_wait(watcher, error=cancel_wait_ex):
    """See :meth:`gevent.hub.Hub.cancel_wait`"""
    get_hub().cancel_wait(watcher, error)


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
    """
    gethostbyname(host) -> address

    Return the IP address (a string of the form '255.255.255.255') for a host.

    .. seealso:: :doc:`dns`
    """
    return get_hub().resolver.gethostbyname(hostname)


def gethostbyname_ex(hostname):
    """
    gethostbyname_ex(host) -> (name, aliaslist, addresslist)

    Return the true host name, a list of aliases, and a list of IP addresses,
    for a host.  The host argument is a string giving a host name or IP number.
    Resolve host and port into list of address info entries.

    .. seealso:: :doc:`dns`
    """
    return get_hub().resolver.gethostbyname_ex(hostname)


def getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    """
    Resolve host and port into list of address info entries.

    Translate the host/port argument into a sequence of 5-tuples that contain
    all the necessary arguments for creating a socket connected to that service.
    host is a domain name, a string representation of an IPv4/v6 address or
    None. port is a string service name such as 'http', a numeric port number or
    None. By passing None as the value of host and port, you can pass NULL to
    the underlying C API.

    The family, type and proto arguments can be optionally specified in order to
    narrow the list of addresses returned. Passing zero as a value for each of
    these arguments selects the full range of results.

    .. seealso:: :doc:`dns`
    """
    return get_hub().resolver.getaddrinfo(host, port, family, socktype, proto, flags)

if PY3:
    # The name of the socktype param changed to type in Python 3.
    # See https://github.com/gevent/gevent/issues/960
    # Using inspect here to directly detect the condition is painful because we have to
    # wrap it with a try/except TypeError because not all Python 2
    # versions can get the args of a builtin; we also have to use a with to suppress
    # the deprecation warning.
    d = getaddrinfo.__doc__

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0): # pylint:disable=function-redefined
        return get_hub().resolver.getaddrinfo(host, port, family, type, proto, flags)
    getaddrinfo.__doc__ = d
    del d


def gethostbyaddr(ip_address):
    """
    gethostbyaddr(ip_address) -> (name, aliaslist, addresslist)

    Return the true host name, a list of aliases, and a list of IP addresses,
    for a host.  The host argument is a string giving a host name or IP number.

    .. seealso:: :doc:`dns`
    """
    return get_hub().resolver.gethostbyaddr(ip_address)


def getnameinfo(sockaddr, flags):
    """
    getnameinfo(sockaddr, flags) -> (host, port)

    Get host and port for a sockaddr.

    .. seealso:: :doc:`dns`
    """
    return get_hub().resolver.getnameinfo(sockaddr, flags)


def getfqdn(name=''):
    """Get fully qualified domain name from name.

    An empty argument is interpreted as meaning the local host.

    First the hostname returned by gethostbyaddr() is checked, then
    possibly existing aliases. In case no FQDN is available, hostname
    from gethostname() is returned.
    """
    # pylint: disable=undefined-variable
    name = name.strip()
    if not name or name == '0.0.0.0':
        name = gethostname()
    try:
        hostname, aliases, _ = gethostbyaddr(name)
    except error:
        pass
    else:
        aliases.insert(0, hostname)
        for name in aliases: # EWW! pylint:disable=redefined-argument-from-local
            if isinstance(name, bytes):
                if b'.' in name:
                    break
            elif '.' in name:
                break
        else:
            name = hostname
    return name
