"""DNS functions based on libevent-dns.

This module contains synchronous wrappers around some of the libevent DNS API.

    >>> dns_resolve_ipv4('localhost')
    ['127.0.0.1']

    >>> dns_resolve_ipv4('www.python.org')
    ['82.94.164.162']

    >>> dns_resolve_reverse('82.94.164.162').endswith('python.org')
    True

The errors are reported through a subclass of :class:`gaierror` - :class:`DNSError`.

    >>> dns_resolve_ipv4('aaaaaaaaaaa')
    Traceback (most recent call last):
     ...
    DNSError: [Errno 3] name does not exist
"""

from gevent import core
from gevent.hub import Waiter
from _socket import gaierror


__all__ = ['DNSError', 'dns_resolve_ipv4', 'dns_resolve_ipv6', 'dns_resolve_reverse', 'dns_resolve_reverse_ipv6']


# move from here into Hub.__init__ (once event_init() is move here as well)
core.dns_init()


class DNSError(gaierror):
    """A DNS error reported by libevent-dns"""

    def __init__(self, *args):
        if len(args)==1:
            code = args[0]
            gaierror.__init__(self, code, core.dns_err_to_string(code))
        else:
            gaierror.__init__(self, *args)


def dns_resolve_ipv4(name, flags=0):
    waiter = Waiter()
    core.dns_resolve_ipv4(name, flags, waiter.switch_args)
    result, _type, _ttl, addrs = waiter.get()
    if result != core.DNS_ERR_NONE:
        raise DNSError(result)
    return addrs
    # QQQ would be nice to have ttl as an attribute


def dns_resolve_ipv6(name, flags=0):
    waiter = Waiter()
    core.dns_resolve_ipv6(name, flags, waiter.switch_args)
    result, _type, _ttl, addrs = waiter.get()
    if result != core.DNS_ERR_NONE:
        raise DNSError(result)
    return addrs


def dns_resolve_reverse(ip, flags=0):
    waiter = Waiter()
    core.dns_resolve_reverse(ip, flags, waiter.switch_args)
    result, _type, _ttl, addr = waiter.get()
    if result != core.DNS_ERR_NONE:
        raise DNSError(result)
    return addr


def dns_resolve_reverse_ipv6(ip, flags=0):
    waiter = Waiter()
    core.dns_resolve_reverse_ipv6(ip, flags, waiter.switch_args)
    result, _type, _ttl, addrs = waiter.get()
    if result != core.DNS_ERR_NONE:
        raise DNSError(result)
    return addrs
