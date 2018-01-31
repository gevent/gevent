# Copyright (c) 2018  gevent contributors. See LICENSE for details.

import _socket
from _socket import AI_NUMERICHOST
from _socket import error
from _socket import NI_NUMERICSERV

import socket

from . import AbstractResolver

from dns import resolver
import dns


__all__ = [
    'Resolver',
]

# This is a copy of resolver._getaddrinfo with the crucial change that it
# doesn't have a bare except:, because that breaks Timeout and KeyboardInterrupt
# See https://github.com/rthalley/dnspython/pull/300
def _getaddrinfo(host=None, service=None, family=socket.AF_UNSPEC, socktype=0,
                 proto=0, flags=0):
    # pylint:disable=too-many-locals,broad-except,too-many-statements
    # pylint:disable=too-many-branches
    # pylint:disable=redefined-argument-from-local
    if flags & (socket.AI_ADDRCONFIG | socket.AI_V4MAPPED) != 0:
        raise NotImplementedError
    if host is None and service is None:
        raise socket.gaierror(socket.EAI_NONAME)
    v6addrs = []
    v4addrs = []
    canonical_name = None
    try:
        # Is host None or a V6 address literal?
        if host is None:
            canonical_name = 'localhost'
            if flags & socket.AI_PASSIVE != 0:
                v6addrs.append('::')
                v4addrs.append('0.0.0.0')
            else:
                v6addrs.append('::1')
                v4addrs.append('127.0.0.1')
        else:
            parts = host.split('%')
            if len(parts) == 2:
                ahost = parts[0]
            else:
                ahost = host
            addr = dns.ipv6.inet_aton(ahost)
            v6addrs.append(host)
            canonical_name = host
    except Exception:
        try:
            # Is it a V4 address literal?
            addr = dns.ipv4.inet_aton(host)
            v4addrs.append(host)
            canonical_name = host
        except Exception:
            if flags & socket.AI_NUMERICHOST == 0:
                try:
                    if family == socket.AF_INET6 or family == socket.AF_UNSPEC:
                        v6 = resolver._resolver.query(host, dns.rdatatype.AAAA,
                                                      raise_on_no_answer=False)
                        # Note that setting host ensures we query the same name
                        # for A as we did for AAAA.
                        host = v6.qname
                        canonical_name = v6.canonical_name.to_text(True)
                        if v6.rrset is not None:
                            for rdata in v6.rrset:
                                v6addrs.append(rdata.address)
                    if family == socket.AF_INET or family == socket.AF_UNSPEC:
                        v4 = resolver._resolver.query(host, dns.rdatatype.A,
                                                      raise_on_no_answer=False)
                        host = v4.qname
                        canonical_name = v4.canonical_name.to_text(True)
                        if v4.rrset is not None:
                            for rdata in v4.rrset:
                                v4addrs.append(rdata.address)
                except dns.resolver.NXDOMAIN:
                    raise socket.gaierror(socket.EAI_NONAME)
                except Exception:
                    raise socket.gaierror(socket.EAI_SYSTEM)
    port = None
    try:
        # Is it a port literal?
        if service is None:
            port = 0
        else:
            port = int(service)
    except Exception:
        if flags & socket.AI_NUMERICSERV == 0:
            try:
                port = socket.getservbyname(service)
            except Exception:
                pass
    if port is None:
        raise socket.gaierror(socket.EAI_NONAME)
    tuples = []
    if socktype == 0:
        socktypes = [socket.SOCK_DGRAM, socket.SOCK_STREAM]
    else:
        socktypes = [socktype]
    if flags & socket.AI_CANONNAME != 0:
        cname = canonical_name
    else:
        cname = ''
    if family == socket.AF_INET6 or family == socket.AF_UNSPEC:
        for addr in v6addrs:
            for socktype in socktypes:
                for proto in resolver._protocols_for_socktype[socktype]:
                    tuples.append((socket.AF_INET6, socktype, proto,
                                   cname, (addr, port, 0, 0)))
    if family == socket.AF_INET or family == socket.AF_UNSPEC:
        for addr in v4addrs:
            for socktype in socktypes:
                for proto in resolver._protocols_for_socktype[socktype]:
                    tuples.append((socket.AF_INET, socktype, proto,
                                   cname, (addr, port)))
    if len(tuples) == 0: # pylint:disable=len-as-condition
        raise socket.gaierror(socket.EAI_NONAME)
    return tuples


class Resolver(AbstractResolver):
    """
    A resolver that uses dnspython.

    This completely ignores the contents of ``/etc/hosts``, but it is
    configured by ``/etc/resolv.conf`` (on Unix) or the registry (on
    Windows).

    This uses thread locks and sockets, so it only functions if the system
    has been monkey-patched. Otherwise it will raise a ``ValueError``.

    Under Python 2, if the ``idna`` package is installed, this resolver
    can resolve Unicode host names that the system resolver cannot.

    .. versionadded:: 1.3a2
    """

    def __init__(self, hub=None): # pylint: disable=unused-argument
        from gevent import monkey
        if not all(monkey.is_module_patched(m) for m in ['threading', 'socket', 'select']):
            raise ValueError("Can only be used when monkey-patched")
        if resolver._resolver is None:
            resolver._resolver = resolver.get_default_resolver()
        if resolver._getaddrinfo is not _getaddrinfo:
            resolver._getaddrinfo = _getaddrinfo

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

        return _getaddrinfo(host, port, family, socktype, proto, flags)

    def getnameinfo(self, sockaddr, flags):
        if (sockaddr
                and isinstance(sockaddr, (list, tuple))
                and sockaddr[0] in ('::1', '127.0.0.1', 'localhost')):
            return _socket.getnameinfo(sockaddr, flags)
        try:
            return resolver._getnameinfo(sockaddr, flags)
        except error:
            if not flags:
                # dnspython doesn't like getting ports it can't resolve.
                # We have one test, test__socket_dns.py:Test_getnameinfo_geventorg.test_port_zero
                # that does this. We conservatively fix it here; this could be expanded later.
                return resolver._getnameinfo(sockaddr, NI_NUMERICSERV)

    def gethostbyaddr(self, ip_address):
        if ip_address in (u'127.0.0.1', u'::1',
                          b'127.0.0.1', b'::1',
                          'localhost'):
            return _socket.gethostbyaddr(ip_address)
        return resolver._gethostbyaddr(ip_address)
