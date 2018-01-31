# Copyright (c) 2018  gevent contributors. See LICENSE for details.

import _socket
from socket import AI_NUMERICHOST
from socket import gaierror

from . import AbstractResolver

from dns import resolver
from dns.resolver import _getaddrinfo

from gevent import Timeout

def _safe_getaddrinfo(*args, **kwargs):
    try:
        return _getaddrinfo(*args, **kwargs)
    except gaierror as ex:
        if isinstance(getattr(ex, '__context__', None),
                      (Timeout, KeyboardInterrupt, SystemExit)):
            raise ex.__context__
        raise

resolver._getaddrinfo = _safe_getaddrinfo

__all__ = [
    'Resolver',
]

class Resolver(AbstractResolver):
    """
    A resolver that uses dnspython.

    This completely ignores the contents of ``/etc/hosts``, but it is
    configured by ``/etc/resolv.conf`` (on Unix) or the registry (on
    Windows).

    This uses thread locks and sockets, so it only functions if the system
    has been monkey-patched. Otherwise it will raise a ``ValueError``.

    This can cause timeouts to be lost: there is a bare `except:` clause
    in the dnspython code that will catch all timeout exceptions gevent raises and
    translate them into socket errors. On Python 3 we can detect this, but
    on Python 2 we cannot.

    .. versionadded:: 1.3a2
    """

    def __init__(self, hub=None): # pylint: disable=unused-argument
        from gevent import monkey
        if not all(monkey.is_module_patched(m) for m in ['threading', 'socket', 'select']):
            raise ValueError("Can only be used when monkey-patched")
        if resolver._resolver is None:
            resolver._resolver = resolver.get_default_resolver()

    def close(self):
        pass

    def getaddrinfo(self, host, port, family=0, socktype=0, proto=0, flags=0):
        if ((host == u'localhost' or host == b'localhost')
                or not isinstance(host, str) or (flags & AI_NUMERICHOST)):
            # this handles cases which do not require network access
            # 1) host is None
            # 2) host is of an invalid type
            # 3) AI_NUMERICHOST flag is set
            return _socket.getaddrinfo(host, port, family, socktype, proto, flags)

        return resolver._getaddrinfo(host, port, family, socktype, proto, flags)

    def getnameinfo(self, sockaddr, flags):
        if sockaddr and isinstance(sockaddr, (list, tuple)) and sockaddr[0] in ('::1', '127.0.0.1'):
            return _socket.getnameinfo(sockaddr, flags)

        return resolver._getnameinfo(sockaddr, flags)

    def gethostbyaddr(self, ip_address):
        if ip_address in (u'127.0.0.1', u'::1',
                          b'127.0.0.1', b'::1',
                          'localhost'):
            return _socket.gethostbyaddr(ip_address)
        return resolver._gethostbyaddr(ip_address)
