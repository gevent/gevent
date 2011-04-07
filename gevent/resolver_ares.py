from _socket import getservbyname, getaddrinfo, gaierror, error
from gevent.hub import Waiter, get_hub, _import
from gevent.socket import AF_UNSPEC, AF_INET, AF_INET6, SOCK_STREAM, SOCK_DGRAM, SOCK_RAW, AI_NUMERICHOST, EAI_SERVICE


__all__ = ['Resolver']


class Resolver(object):

    ares_class = 'gevent.core.ares_channel'

    def __init__(self, hub=None, ares=None):
        if hub is None:
            hub = get_hub()
        self.hub = hub
        if ares is None:
            ares_class = _import(self.ares_class)
            ares = ares_class(hub.loop)
        self.ares = ares

    def gethostbyname(self, hostname, family=AF_INET):
        return self.gethostbyname_ex(hostname, family)[-1][0]

    def gethostbyname_ex(self, hostname, family=AF_INET):
        waiter = Waiter(self.hub)
        self.ares.gethostbyname(waiter, hostname, family)
        return waiter.get()

    def getaddrinfo(self, host, port, family=0, socktype=0, proto=0, flags=0):
        if isinstance(host, unicode):
            host = host.encode('idna')
        elif not isinstance(host, str) or (flags & AI_NUMERICHOST):
            # this handles cases which do not require network access
            # 1) host is None
            # 2) host is of an invalid type
            # 3) AI_NUMERICHOST flag is set
            return getaddrinfo(host, port, family, socktype, proto, flags)
            # we also call _socket.getaddrinfo below if family is not one of AF_*
        if isinstance(port, basestring):
            try:
                if socktype == 0:
                    try:
                        port = getservbyname(port, 'tcp')
                        socktype = SOCK_STREAM
                    except error:
                        port = getservbyname(port, 'udp')
                        socktype = SOCK_DGRAM
                elif socktype == SOCK_STREAM:
                    port = getservbyname(port, 'tcp')
                elif socktype == SOCK_DGRAM:
                    port = getservbyname(port, 'udp')
                else:
                    raise gaierror(EAI_SERVICE, 'Servname not supported for ai_socktype')
            except error, ex:
                if 'not found' in str(ex):
                    raise gaierror(EAI_SERVICE, 'Servname not supported for ai_socktype')
                else:
                    raise gaierror(str(ex))
        elif port is None:
            port = 0

        socktype_proto = [(SOCK_STREAM, 6), (SOCK_DGRAM, 17), (SOCK_RAW, 0)]
        if socktype:
            socktype_proto = [(x, y) for (x, y) in socktype_proto if socktype == x]
        if proto:
            socktype_proto = [(x, y) for (x, y) in socktype_proto if proto == y]

        if family == AF_UNSPEC:
            values = Values(2)
            self.ares.gethostbyname(values, host, AF_INET)
            self.ares.gethostbyname(values, host, AF_INET6)
        elif family == AF_INET:
            values = Values(1)
            self.ares.gethostbyname(values, host, AF_INET)
        elif family == AF_INET6:
            values = Values(1)
            self.ares.gethostbyname(values, host, AF_INET6)
        else:
            # most likely will raise the exception, let the original getaddrinfo do it
            return getaddrinfo(host, port, family, socktype, proto, flags)

        values = values.get()
        if len(values) == 2 and values[0] == values[1]:
            values.pop()
        result = []

        try:
            for addrs in values:
                if addrs.family == AF_INET:
                    for addr in addrs[-1]:
                        sockaddr = (addr, port)
                        for socktype, proto in socktype_proto:
                            result.append((AF_INET, socktype, proto, '', sockaddr))
                elif addrs.family == AF_INET6:
                    for addr in addrs[-1]:
                        sockaddr = (addr, port, 0, 0)
                        for socktype, proto in socktype_proto:
                            result.append((AF_INET6, socktype, proto, '', sockaddr))
                else:
                    raise error('Internal error in %s' % self.ares.gethostbyname)
        except error:
            if not result:
                raise
        return result

    def gethostbyaddr(self, ip_address):
        waiter = Waiter(self.hub)
        self.ares.gethostbyaddr(waiter, ip_address)
        try:
            return waiter.get()
        except ValueError, ex:
            if not str(ex).startswith('illegal IP'):
                raise
            # socket.gethostbyaddr also accepts domain names; let's do that too
            _ip_address = self.gethostbyname(ip_address, 0)
            if _ip_address == ip_address:
                raise
            waiter.clear()
            self.ares.gethostbyaddr(waiter, _ip_address)
            return waiter.get()

    def getnameinfo(self, sockaddr, flags):
        waiter = Waiter(self.hub)
        self.ares.getnameinfo(waiter, sockaddr, flags)
        try:
            result = waiter.get()
        except ValueError, ex:
            if not str(ex).startswith('illegal IP'):
                raise
            # socket.getnameinfo also accepts domain names; let's do that too
            _ip_address = self.gethostbyname(sockaddr[0], 0)
            if _ip_address == sockaddr[0]:
                raise
            waiter.clear()
            self.ares.getnameinfo(waiter, (_ip_address, ) + sockaddr[1:], flags)
            result = waiter.get()
        if result[1] is None:
            return (result[0], str(sockaddr[1])) + result[2:]
        return result


class Values(object):
    # helper to collect multiple values; ignore errors unless nothing has succeeded
    # QQQ could probable be moved somewhere - hub.py?

    __slots__ = ['count', 'values', 'error', 'waiter']

    def __init__(self, count=1):
        self.count = count
        self.values = []
        self.error = None
        self.waiter = Waiter()

    def __call__(self, source):
        self.count -= 1
        if source.exception is None:
            self.values.append(source.value)
        else:
            self.error = source.exception
        if self.count <= 0:
            self.waiter.switch()

    def get(self):
        self.waiter.get()
        if self.values:
            return self.values
        else:
            raise self.error
