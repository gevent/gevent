# Copyright (c) 2018  gevent contributors. See LICENSE for details.

# Portions of this code taken from the gogreen project:
#   http://github.com/slideinc/gogreen
#
# Copyright (c) 2005-2010 Slide, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of the author nor the names of other
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Portions of this code taken from the eventlet project:
# https://github.com/eventlet/eventlet/blob/master/eventlet/support/greendns.py

# Unless otherwise noted, the files in Eventlet are under the following MIT license:

# Copyright (c) 2005-2006, Bob Ippolito
# Copyright (c) 2007-2010, Linden Research, Inc.
# Copyright (c) 2008-2010, Eventlet Contributors (see AUTHORS)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from __future__ import absolute_import, print_function, division

import time
import re
import os
import sys

import _socket
from _socket import AI_NUMERICHOST
from _socket import error
from _socket import NI_NUMERICSERV
from _socket import AF_INET
from _socket import AF_INET6
from _socket import AF_UNSPEC

import socket

from gevent.resolver import AbstractResolver
from gevent.resolver import hostname_types

from gevent._compat import string_types
from gevent._compat import iteritems
from gevent._patcher import import_patched
from gevent._config import config

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
dTimeout = dns.resolver.Timeout

_exc_clear = getattr(sys, 'exc_clear', lambda: None)

# This is a copy of resolver._getaddrinfo with the crucial change that it
# doesn't have a bare except:, because that breaks Timeout and KeyboardInterrupt
# A secondary change is that calls to sys.exc_clear() have been inserted to avoid
# failing tests in test__refcount.py (timeouts).
# See https://github.com/rthalley/dnspython/pull/300
def _getaddrinfo(host=None, service=None, family=AF_UNSPEC, socktype=0,
                 proto=0, flags=0):
    # pylint:disable=too-many-locals,broad-except,too-many-statements
    # pylint:disable=too-many-branches
    # pylint:disable=redefined-argument-from-local
    # pylint:disable=consider-using-in
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
        _exc_clear()
        try:
            # Is it a V4 address literal?
            addr = dns.ipv4.inet_aton(host)
            v4addrs.append(host)
            canonical_name = host
        except Exception:
            _exc_clear()
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
                    _exc_clear()
                    raise socket.gaierror(socket.EAI_NONAME)
                except Exception:
                    _exc_clear()
                    raise socket.gaierror(socket.EAI_SYSTEM)
    port = None
    try:
        # Is it a port literal?
        if service is None:
            port = 0
        else:
            port = int(service)
    except Exception:
        _exc_clear()
        if flags & socket.AI_NUMERICSERV == 0:
            try:
                port = socket.getservbyname(service)
            except Exception:
                _exc_clear()

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
                                   cname, (addr, port, 0, 0))) # XXX: gevent: this can get the scopeid wrong
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

HOSTS_TTL = 300.0

def _is_addr(host, parse=dns.ipv4.inet_aton):
    if not host:
        return False
    assert isinstance(host, hostname_types), repr(host)
    try:
        parse(host)
    except dns.exception.SyntaxError:
        return False
    else:
        return True

# Return True if host is a valid IPv4 address
_is_ipv4_addr = _is_addr


def _is_ipv6_addr(host):
    # Return True if host is a valid IPv6 address
    if host:
        s = '%' if isinstance(host, str) else b'%'
        host = host.split(s, 1)[0]
    return _is_addr(host, dns.ipv6.inet_aton)

class HostsFile(object):
    """
    A class to read the contents of a hosts file (/etc/hosts).
    """

    LINES_RE = re.compile(r"""
        \s*  # Leading space
        ([^\r\n#]+?)  # The actual match, non-greedy so as not to include trailing space
        \s*  # Trailing space
        (?:[#][^\r\n]+)?  # Comments
        (?:$|[\r\n]+)  # EOF or newline
    """, re.VERBOSE)

    def __init__(self, fname=None):
        self.v4 = {} # name -> ipv4
        self.v6 = {} # name -> ipv6
        self.aliases = {} # name -> canonical_name
        self.reverse = {} # ip addr -> some name
        if fname is None:
            if os.name == 'posix':
                fname = '/etc/hosts'
            elif os.name == 'nt': # pragma: no cover
                fname = os.path.expandvars(
                    r'%SystemRoot%\system32\drivers\etc\hosts')
        self.fname = fname
        assert self.fname
        self._last_load = 0


    def _readlines(self):
        # Read the contents of the hosts file.
        #
        # Return list of lines, comment lines and empty lines are
        # excluded. Note that this performs disk I/O so can be
        # blocking.
        with open(self.fname, 'rb') as fp:
            fdata = fp.read()


        # XXX: Using default decoding. Is that correct?
        udata = fdata.decode(errors='ignore') if not isinstance(fdata, str) else fdata

        return self.LINES_RE.findall(udata)

    def load(self): # pylint:disable=too-many-locals
        # Load hosts file

        # This will (re)load the data from the hosts
        # file if it has changed.

        try:
            load_time = os.stat(self.fname).st_mtime
            needs_load = load_time > self._last_load
        except (IOError, OSError):
            from gevent import get_hub
            get_hub().handle_error(self, *sys.exc_info())
            needs_load = False

        if not needs_load:
            return

        v4 = {}
        v6 = {}
        aliases = {}
        reverse = {}

        for line in self._readlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            ip = parts.pop(0)
            if _is_ipv4_addr(ip):
                ipmap = v4
            elif _is_ipv6_addr(ip):
                if ip.startswith('fe80'):
                    # Do not use link-local addresses, OSX stores these here
                    continue
                ipmap = v6
            else:
                continue
            cname = parts.pop(0).lower()
            ipmap[cname] = ip
            for alias in parts:
                alias = alias.lower()
                ipmap[alias] = ip
                aliases[alias] = cname

            # XXX: This is wrong for ipv6
            if ipmap is v4:
                ptr = '.'.join(reversed(ip.split('.'))) + '.in-addr.arpa'
            else:
                ptr = ip + '.ip6.arpa.'
            if ptr not in reverse:
                reverse[ptr] = cname

        self._last_load = load_time
        self.v4 = v4
        self.v6 = v6
        self.aliases = aliases
        self.reverse = reverse

    def iter_all_host_addr_pairs(self):
        self.load()
        for name, addr in iteritems(self.v4):
            yield name, addr
        for name, addr in iteritems(self.v6):
            yield name, addr

class _HostsAnswer(dns.resolver.Answer):
    # Answer class for HostsResolver object

    def __init__(self, qname, rdtype, rdclass, rrset, raise_on_no_answer=True):
        self.response = None
        self.qname = qname
        self.rdtype = rdtype
        self.rdclass = rdclass
        self.canonical_name = qname
        if not rrset and raise_on_no_answer:
            raise dns.resolver.NoAnswer()
        self.rrset = rrset
        self.expiration = (time.time() +
                           rrset.ttl if hasattr(rrset, 'ttl') else 0)


class _HostsResolver(object):
    """
    Class to parse the hosts file
    """

    def __init__(self, fname=None, interval=HOSTS_TTL):
        self.hosts_file = HostsFile(fname)
        self.interval = interval
        self._last_load = 0

    def query(self, qname, rdtype=dns.rdatatype.A, rdclass=dns.rdataclass.IN,
              tcp=False, source=None, raise_on_no_answer=True): # pylint:disable=unused-argument
        # Query the hosts file
        #
        # The known rdtypes are dns.rdatatype.A, dns.rdatatype.AAAA and
        # dns.rdatatype.CNAME.
        # The ``rdclass`` parameter must be dns.rdataclass.IN while the
        # ``tcp`` and ``source`` parameters are ignored.
        # Return a HostAnswer instance or raise a dns.resolver.NoAnswer
        # exception.

        now = time.time()
        hosts_file = self.hosts_file
        if self._last_load + self.interval < now:
            self._last_load = now
            hosts_file.load()

        rdclass = dns.rdataclass.IN # Always
        if isinstance(qname, string_types):
            name = qname
            qname = dns.name.from_text(qname)
        else:
            name = str(qname)

        name = name.lower()
        rrset = dns.rrset.RRset(qname, rdclass, rdtype)
        rrset.ttl = self._last_load + self.interval - now

        if rdtype == dns.rdatatype.A:
            mapping = hosts_file.v4
            kind = dns.rdtypes.IN.A.A
        elif rdtype == dns.rdatatype.AAAA:
            mapping = hosts_file.v6
            kind = dns.rdtypes.IN.AAAA.AAAA
        elif rdtype == dns.rdatatype.CNAME:
            mapping = hosts_file.aliases
            kind = lambda c, t, addr: dns.rdtypes.ANY.CNAME.CNAME(c, t, dns.name.from_text(addr))
        elif rdtype == dns.rdatatype.PTR:
            mapping = hosts_file.reverse
            kind = lambda c, t, addr: dns.rdtypes.ANY.PTR.PTR(c, t, dns.name.from_text(addr))


        addr = mapping.get(name)
        if not addr and qname.is_absolute():
            addr = mapping.get(name[:-1])
        if addr:
            rrset.add(kind(rdclass, rdtype, addr))
        return _HostsAnswer(qname, rdtype, rdclass, rrset, raise_on_no_answer)

    def getaliases(self, hostname):
        # Return a list of all the aliases of a given cname

        # Due to the way store aliases this is a bit inefficient, this
        # clearly was an afterthought.  But this is only used by
        # gethostbyname_ex so it's probably fine.
        aliases = self.hosts_file.aliases
        result = []
        if hostname in aliases:
            cannon = aliases[hostname]
        else:
            cannon = hostname
        result.append(cannon)
        for alias, cname in iteritems(aliases):
            if cannon == cname:
                result.append(alias)
        result.remove(hostname)
        return result

class _DualResolver(object):

    def __init__(self):
        self.hosts_resolver = _HostsResolver()
        self.network_resolver = resolver.get_default_resolver()
        self.network_resolver.cache = resolver.LRUCache()

    def query(self, qname, rdtype=dns.rdatatype.A, rdclass=dns.rdataclass.IN,
              tcp=False, source=None, raise_on_no_answer=True,
              _hosts_rdtypes=(dns.rdatatype.A, dns.rdatatype.AAAA, dns.rdatatype.PTR)):
        # Query the resolver, using /etc/hosts

        # Behavior:
        # 1. if hosts is enabled and contains answer, return it now
        # 2. query nameservers for qname
        if qname is None:
            qname = '0.0.0.0'

        if not isinstance(qname, string_types):
            if isinstance(qname, bytes):
                qname = qname.decode("idna")

        if isinstance(qname, string_types):
            qname = dns.name.from_text(qname, None)

        if isinstance(rdtype, string_types):
            rdtype = dns.rdatatype.from_text(rdtype)

        if rdclass == dns.rdataclass.IN and rdtype in _hosts_rdtypes:
            try:
                answer = self.hosts_resolver.query(qname, rdtype, raise_on_no_answer=False)
            except Exception: # pylint: disable=broad-except
                from gevent import get_hub
                get_hub().handle_error(self, *sys.exc_info())
            else:
                if answer.rrset:
                    return answer

        return self.network_resolver.query(qname, rdtype, rdclass,
                                           tcp, source, raise_on_no_answer=raise_on_no_answer)

def _family_to_rdtype(family):
    if family == socket.AF_INET:
        rdtype = dns.rdatatype.A
    elif family == socket.AF_INET6:
        rdtype = dns.rdatatype.AAAA
    else:
        raise socket.gaierror(socket.EAI_FAMILY,
                              'Address family not supported')
    return rdtype

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
            _resolver = resolver._resolver = _DualResolver()
            if config.resolver_nameservers:
                _resolver.network_resolver.nameservers[:] = config.resolver_nameservers
            if config.resolver_timeout:
                _resolver.network_resolver.lifetime = config.resolver_timeout
        # Different hubs in different threads could be sharing the same
        # resolver.
        assert isinstance(resolver._resolver, _DualResolver)
        self._resolver = resolver._resolver

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
        return self._resolver.network_resolver

    def close(self):
        pass

    def _getaliases(self, hostname, family):
        if not isinstance(hostname, str):
            if isinstance(hostname, bytes):
                hostname = hostname.decode("idna")
        aliases = self._resolver.hosts_resolver.getaliases(hostname)
        net_resolver = self._resolver.network_resolver
        rdtype = _family_to_rdtype(family)
        while True:
            try:
                ans = net_resolver.query(hostname, dns.rdatatype.CNAME, rdtype)
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                break
            except dTimeout:
                break
            else:
                aliases.extend(str(rr.target) for rr in ans.rrset)
                hostname = ans[0].target
        return aliases

    def getaddrinfo(self, host, port, family=0, socktype=0, proto=0, flags=0):
        if ((host in (u'localhost', b'localhost')
             or (_is_ipv6_addr(host) and host.startswith('fe80')))
                or not isinstance(host, str) or (flags & AI_NUMERICHOST)):
            # this handles cases which do not require network access
            # 1) host is None
            # 2) host is of an invalid type
            # 3) host is localhost or a link-local ipv6; dnspython returns the wrong
            #    scope-id for those.
            # 3) AI_NUMERICHOST flag is set

            return _socket.getaddrinfo(host, port, family, socktype, proto, flags)

        if family == AF_UNSPEC:
            # This tends to raise in the case that a v6 address did not exist
            # but a v4 does. So we break it into two parts.

            # Note that if there is no ipv6 in the hosts file, but there *is*
            # an ipv4, and there *is* an ipv6 in the nameservers, we will return
            # both (from the first call). The system resolver on OS X only returns
            # the results from the hosts file. doubleclick.com is one example.

            # See also https://github.com/gevent/gevent/issues/1012
            try:
                return _getaddrinfo(host, port, family, socktype, proto, flags)
            except socket.gaierror:
                try:
                    return _getaddrinfo(host, port, AF_INET6, socktype, proto, flags)
                except socket.gaierror:
                    return _getaddrinfo(host, port, AF_INET, socktype, proto, flags)
        else:
            return _getaddrinfo(host, port, family, socktype, proto, flags)

    def getnameinfo(self, sockaddr, flags):
        if (sockaddr
                and isinstance(sockaddr, (list, tuple))
                and sockaddr[0] in ('::1', '127.0.0.1', 'localhost')):
            return _socket.getnameinfo(sockaddr, flags)
        if isinstance(sockaddr, (list, tuple)) and not isinstance(sockaddr[0], hostname_types):
            raise TypeError("getnameinfo(): illegal sockaddr argument")
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

        if not isinstance(ip_address, hostname_types):
            raise TypeError("argument 1 must be str, bytes or bytearray, not %s" % (type(ip_address),))

        return resolver._gethostbyaddr(ip_address)
