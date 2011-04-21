__all__ += ['dns_init', 'dns_shutdown', 'dns_err_to_string',
            'dns_resolve_ipv4', 'dns_resolve_ipv6',
            'dns_resolve_reverse', 'dns_resolve_reverse_ipv6']

cdef extern from *:
    ctypedef char* const_char_ptr "const char*"

cdef extern from "libevent.h":
    ctypedef void (*evdns_handler)(int result, char t, int count, int ttl, void *addrs, void *arg)

    int evdns_init()
    const_char_ptr evdns_err_to_string(int err)
    int evdns_resolve_ipv4(char *name, int flags, evdns_handler callback, void *arg)
    int evdns_resolve_ipv6(char *name, int flags, evdns_handler callback, void *arg)
    int evdns_resolve_reverse(void *ip, int flags, evdns_handler callback, void *arg)
    int evdns_resolve_reverse_ipv6(void *ip, int flags, evdns_handler callback, void *arg)
    void evdns_shutdown(int fail_requests)

# Result codes
DNS_ERR_NONE         = 0
DNS_ERR_FORMAT       = 1
DNS_ERR_SERVERFAILED = 2
DNS_ERR_NOTEXIST     = 3
DNS_ERR_NOTIMPL      = 4
DNS_ERR_REFUSED      = 5
DNS_ERR_TRUNCATED    = 65
DNS_ERR_UNKNOWN      = 66
DNS_ERR_TIMEOUT      = 67
DNS_ERR_SHUTDOWN     = 68

# Types
DNS_IPv4_A    = 1
DNS_PTR       = 2
DNS_IPv6_AAAA = 3

# Flags
DNS_QUERY_NO_SEARCH = 1


def dns_init():
    """Initialize async DNS resolver."""
    evdns_init()


def dns_shutdown(int fail_requests=0):
    """Shutdown the async DNS resolver and terminate all active requests."""
    evdns_shutdown(fail_requests)


def dns_err_to_string(int err):
    cdef const_char_ptr result = evdns_err_to_string(err)
    if result:
        return result


cdef void __evdns_callback(int code, char type, int count, int ttl, void *addrs, void *arg) with gil:
    cdef int i
    cdef object callback = <object>arg
    Py_DECREF(<PyObjectPtr>callback)
    cdef object addr
    cdef object result

    if type == DNS_IPv4_A:
        result = []
        for i from 0 <= i < count:
            addr = PyString_FromStringAndSize(&(<char *>addrs)[i*4], 4)
            result.append(addr)
    elif type == DNS_IPv6_AAAA:
        result = []
        for i from 0 <= i < count:
            addr = PyString_FromStringAndSize(&(<char *>addrs)[i*16], 16)
            result.append(addr)
    elif type == DNS_PTR and count == 1: # only 1 PTR possible
        result = PyString_FromString((<char **>addrs)[0])
    else:
        result = None
    try:
        callback(code, type, ttl, result)
    except:
        traceback.print_exc()
        sys.exc_clear()


def dns_resolve_ipv4(char *name, int flags, object callback):
    """Lookup an A record for a given name.

    - *name*     -- DNS hostname
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs)`` prototype
    """
    cdef int result = evdns_resolve_ipv4(name, flags, __evdns_callback, <void *>callback)
    if result:
        raise IOError('evdns_resolve_ipv4(%r, %r) returned %s' % (name, flags, result, ))
    Py_INCREF(<PyObjectPtr>callback)


def dns_resolve_ipv6(char *name, int flags, object callback):
    """Lookup an AAAA record for a given name.

    - *name*     -- DNS hostname
    - *flags*    -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback* -- callback with ``(result, type, ttl, addrs)`` prototype
    """
    cdef int result = evdns_resolve_ipv6(name, flags, __evdns_callback, <void *>callback)
    if result:
        raise IOError('evdns_resolve_ip6(%r, %r) returned %s' % (name, flags, result, ))
    Py_INCREF(<PyObjectPtr>callback)


def dns_resolve_reverse(char* packed_ip, int flags, object callback):
    """Lookup a PTR record for a given IPv4 address.

    - *packed_ip* -- IPv4 address (as 4-byte binary string)
    - *flags*     -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback*  -- callback with ``(result, type, ttl, addrs)`` prototype
    """
    cdef int result = evdns_resolve_reverse(<void *>packed_ip, flags, __evdns_callback, <void *>callback)
    if result:
        raise IOError('evdns_resolve_reverse(%r, %r) returned %s' % (packed_ip, flags, result, ))
    Py_INCREF(<PyObjectPtr>callback)


def dns_resolve_reverse_ipv6(char* packed_ip, int flags, object callback):
    """Lookup a PTR record for a given IPv6 address.

    - *packed_ip* -- IPv6 address (as 16-byte binary string)
    - *flags*     -- either 0 or DNS_QUERY_NO_SEARCH
    - *callback*  -- callback with ``(result, type, ttl, addrs)`` prototype
    """
    cdef int result = evdns_resolve_reverse_ipv6(<void *>packed_ip, flags, __evdns_callback, <void *>callback)
    if result:
        raise IOError('evdns_resolve_reverse_ipv6(%r, %r) returned %s' % (packed_ip, flags, result, ))
    Py_INCREF(<PyObjectPtr>callback)
