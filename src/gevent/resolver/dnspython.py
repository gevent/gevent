# Copyright (c) 2018  gevent contributors. See LICENSE for details.


import _socket
from _socket import AI_NUMERICHOST
from _socket import error
from _socket import NI_NUMERICSERV

import socket

from . import AbstractResolver

from gevent._patcher import import_patched

__all__ = [
    'Resolver',
]

# Import the DNS packages to use the gevent modules,
# even if the system is not monkey-patched.
def _patch_dns():
    top = import_patched('dns')
    for pkg in ('dns',
                'dns.rdtypes',
                'dns.rdtypes.IN',
                'dns.rdtypes.ANY'):
        mod = import_patched(pkg)
        for name in mod.__all__:
            setattr(mod, name, import_patched(pkg + '.' + name))
    return top

dns = _patch_dns()

def _dns_import_patched(name):
    assert name.startswith('dns')
    import_patched(name)
    return dns

# This module tries to dynamically import classes
# using __import__, and it's important that they match
# the ones we just created, otherwise exceptions won't be caught
# as expected. It uses a one-arg __import__ statement and then
# tries to walk down the sub-modules using getattr, so we can't
# directly use import_patched as-is.
dns.rdata.__import__ = _dns_import_patched

resolver = dns.resolver


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


resolver._getaddrinfo = _getaddrinfo

class Resolver(AbstractResolver):
    """
    An *experimental* resolver that uses `dnspython`_.

    This is typically slower than the default threaded resolver
    (unless there's a cache hit, in which case it can be much faster).
    It is usually much faster than the c-ares resolver. It tends to
    scale well as more concurrent resolutions are attempted.

    Under Python 2, if the ``idna`` package is installed, this
    resolver can resolve Unicode host names that the system resolver
    cannot.

    .. note::

        This **does not** use dnspython's default resolver object, or share any
        classes with ``import dns``. A separate copy of the objects is imported to
        be able to function in a non monkey-patched process. The documentation for the resolver
        object still applies.

        The resolver that we use is available as the :attr:`resolver` attribute
        of this object (typically ``gevent.get_hub().resolver.resolver``).

    .. caution::

        This completely ignores the contents of ``/etc/hosts``, but it is
        configured by ``/etc/resolv.conf`` (on Unix) or the registry (on
        Windows). There are some measures in place to be able to resolve
        ``localhost`` related names and addresses through the system resolver.

        Many of the same caveats about DNS results apply here as are documented
        for :class:`gevent.resolver.ares.Resolver`.

    .. caution::

        This resolver is experimental. It may be removed or modified in
        the future. As always, feedback is welcome.

    .. versionadded:: 1.3a2

    .. _dnspython: http://www.dnspython.org
    """

    def __init__(self, hub=None): # pylint: disable=unused-argument
        if resolver._resolver is None:
            resolver._resolver = resolver.get_default_resolver()
            # Add a default cache
            resolver._resolver.cache = resolver.LRUCache()

    @property
    def resolver(self):
        """
        The dnspython resolver object we use.

        This object has several useful attributes that can be used to
        adjust the behaviour of the DNS system:

        * ``cache`` is a :class:`dns.resolver.LRUCache`. Its maximum size
          can be configured by calling :meth:`resolver.cache.set_max_size`
        * ``nameservers`` controls which nameservers to talk to
        * ``lifetime`` configures a timeout for each individual query.
        """
        return resolver._resolver

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
