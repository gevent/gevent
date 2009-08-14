cdef extern from "arpa/inet.h":
    struct in_addr
    char *inet_ntoa(in_addr n)

cdef extern from "evdns.h":
    ctypedef void (*evdns_handler)(int result, char t, int count, int ttl,
                                   void *addrs, void *arg)

    int evdns_init()
    char *evdns_err_to_string(int err)
    int evdns_resolve_ipv4(char *name, int flags, evdns_handler callback,
                           void *arg)
    int evdns_resolve_ipv6(char *name, int flags, evdns_handler callback,
                           void *arg)
    int evdns_resolve_reverse(char *ip, int flags, evdns_handler callback,
                              void *arg)
    int evdns_resolve_reverse_ipv6(char *ip, int flags, evdns_handler callback,
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
    #__evdns_cbargs.clear()

cdef void __evdns_callback(int result, char t, int count, int ttl,
                     void *addrs, void *arg) with gil:
    cdef int i
    cdef in_addr *inaddrs
    ctx = <tuple>(arg)
    (callback, args) = ctx
    Py_DECREF(ctx)

    if t == DNS_IPv4_A:
        x = []
        inaddrs = <in_addr *>addrs
        for i from 0 <= i < count:
            #x.append(PyString_FromStringAndSize(<char *>addrs + (i * 4), 4))
            x.append(PyString_FromString(inet_ntoa(inaddrs[i])))
    elif t == DNS_IPv6_AAAA:
        x = []
        for i from 0 <= i < count:
            x.append(PyString_FromStringAndSize(<char *>addrs + (i * 16), 16))
    elif t == DNS_PTR and count == 1: # only 1 PTR possible
        x = PyString_FromString((<char **>addrs)[0])
    else:
        x = None
    try:
        callback(result, t, ttl, x, args)
    except:
        # JJJ commented this out and added trackback print
        #__event_abort()
        traceback.print_exc()

    
def dns_resolve_ipv4(char *name, int flags, callback, *args):
    """Lookup an A record for a given name.

    Arguments:

    name     -- DNS hostname
    flags    -- either 0 or DNS_QUERY_NO_SEARCH
    callback -- callback with (result, type, ttl, addrs, *args) prototype
    args     -- option callback arguments
    """
    cdef long long i
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_ipv4(name, flags, __evdns_callback, <void *>t)

def dns_resolve_ipv6(char *name, int flags, callback, *args):
    """Lookup an AAAA record for a given name.

    Arguments:

    name     -- DNS hostname
    flags    -- either 0 or DNS_QUERY_NO_SEARCH
    callback -- callback with (result, type, ttl, addrs, *args) prototype
    args     -- option callback arguments
    """
    cdef long long i
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_ipv6(name, flags, __evdns_callback, <void *>t)

def dns_resolve_reverse(char *ip, int flags, callback, *args):
    """Lookup a PTR record for a given IPv4 address.

    Arguments:

    name     -- IPv4 address (as 4-byte binary string)
    flags    -- either 0 or DNS_QUERY_NO_SEARCH
    callback -- callback with (result, type, ttl, addrs, *args) prototype
    args     -- option callback arguments
    """
    cdef long long i
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_reverse(ip, flags, __evdns_callback, <void *>t)

def dns_resolve_reverse_ipv6(char *ip, int flags, callback, *args):
    """Lookup a PTR record for a given IPv6 address.

    Arguments:

    name     -- IPv6 address (as 16-byte binary string)
    flags    -- either 0 or DNS_QUERY_NO_SEARCH
    callback -- callback with (result, type, ttl, addrs, *args) prototype
    args     -- option callback arguments
    """
    cdef long long i
    t = (callback, args)
    Py_INCREF(t)
    evdns_resolve_reverse(ip, flags, __evdns_callback, <void *>t)

def dns_shutdown(int fail_requests=0):
    """Shutdown the async DNS resolver and terminate all active requests."""
    evdns_shutdown(fail_requests)

