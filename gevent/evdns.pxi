__all__ += ['dns_init', 'dns_shutdown', 'dns_resolve_ipv4', 'dns_resolve_ipv6',
            'dns_resolve_reverse', 'dns_resolve_reverse_ipv6', 'dns_shutdown']

cdef extern from "netinet/in.h":
    cdef enum:
        INET6_ADDRSTRLEN

cdef extern from "sys/socket.h":
    cdef enum:
        AF_INET
        AF_INET6

cdef extern from "arpa/inet.h":
    struct in_addr:
        pass
    struct in6_addr:
        pass
    ctypedef int socklen_t
    char *inet_ntoa(in_addr n)
    int inet_aton(char *cp, in_addr *inp)
    int inet_pton(int af, char *src, void *dst)
    char *inet_ntop(int af, void *src, char *dst, socklen_t size)

cdef extern from "libevent.h":
    ctypedef void (*evdns_handler)(int result, char t, int count, int ttl,
                                   void *addrs, void *arg)

    int evdns_init()
    char *evdns_err_to_string(int err)
    int evdns_resolve_ipv4(char *name, int flags, evdns_handler callback,
                           void *arg)
    int evdns_resolve_ipv6(char *name, int flags, evdns_handler callback,
                           void *arg)
    int evdns_resolve_reverse(in_addr *ip, int flags, evdns_handler callback,
                              void *arg)
    int evdns_resolve_reverse_ipv6(in6_addr *ip, int flags, evdns_handler callback,
                                   void *arg)
    void evdns_shutdown(int fail_requests)

# Result codes
DNS_ERR_NONE		= 0
DNS_ERR_FORMAT		= 1
DNS_ERR_SERVERFAILED	= 2
DNS_ERR_NOTEXIST	= 3
DNS_ERR_NOTIMPL		= 4
DNS_ERR_REFUSED		= 5
DNS_ERR_TRUNCATED	= 65
DNS_ERR_UNKNOWN		= 66
DNS_ERR_TIMEOUT		= 67
DNS_ERR_SHUTDOWN	= 68

# Types
DNS_IPv4_A		= 1
DNS_PTR			= 2
DNS_IPv6_AAAA		= 3

# Flags
DNS_QUERY_NO_SEARCH	= 1

def dns_init():
    """Initialize async DNS resolver."""
    evdns_init()

cdef void __evdns_callback(int result, char t, int count, int ttl,
                     void *addrs, void *arg) with gil:
    cdef int i
    cdef char str[INET6_ADDRSTRLEN]
    ctx = <tuple>(arg)
    (callback, args) = ctx
    Py_DECREF(ctx)

    if t == DNS_IPv4_A:
        x = []
        for i from 0 <= i < count:
            x.append(PyString_FromString(inet_ntoa((<in_addr *>addrs)[i])))
    elif t == DNS_IPv6_AAAA:
        x = []
        for i from 0 <= i < count:
            x.append(PyString_FromString(inet_ntop(AF_INET6, <void *>&(<in6_addr *>addrs)[i], str, sizeof(str))))
    elif t == DNS_PTR and count == 1: # only 1 PTR possible
        x = PyString_FromString((<char **>addrs)[0])
    else:
        x = None
    try:
        callback(result, t, ttl, x, args)
    except:
        traceback.print_exc()

    
def dns_resolve_ipv4(char *name, int flags, callback, *args):
    """Lookup an A record for a given name.

    - *name*     -- DNS hostname
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs, *args)`` prototype
    - *args*     -- option callback arguments
    """
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_ipv4(name, flags, __evdns_callback, <void *>t)

def dns_resolve_ipv6(char *name, int flags, callback, *args):
    """Lookup an AAAA record for a given name.

    - *name*     -- DNS hostname
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs, *args)`` prototype
    - *args*     -- option callback arguments
    """
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_ipv6(name, flags, __evdns_callback, <void *>t)

def dns_resolve_reverse(char *ip, int flags, callback, *args):
    """Lookup a PTR record for a given IPv4 address.

    - *name*     -- IPv4 address (as 4-byte binary string)
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs, *args)`` prototype
    - *args*     -- option callback arguments
    """
    t = (callback, args)
    Py_INCREF(t)
    cdef in_addr addr
    inet_aton(ip, &addr)
    evdns_resolve_reverse(&addr, flags, __evdns_callback, <void *>t)

def dns_resolve_reverse_ipv6(char *ip, int flags, callback, *args):
    """Lookup a PTR record for a given IPv6 address.

    - *name*     -- IPv6 address (as 16-byte binary string)
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs, *args)`` prototype
    - *args*     -- option callback arguments
    """
    t = (callback, args)
    Py_INCREF(t)
    cdef in6_addr addr
    inet_pton(AF_INET6, ip, &addr)
    evdns_resolve_reverse_ipv6(&addr, flags, __evdns_callback, <void *>t)

def dns_shutdown(int fail_requests=0):
    """Shutdown the async DNS resolver and terminate all active requests."""
    evdns_shutdown(fail_requests)

