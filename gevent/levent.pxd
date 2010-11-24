ctypedef void (*event_handler)(int fd, short evtype, void *arg)
ctypedef void (*event_log_cb)(int severity, char *msg)

cdef extern from "libevent.h":

    # event.h:
    struct timeval:
        unsigned int tv_sec
        unsigned int tv_usec

    struct event:
        void* ev_base
        int   ev_fd
        short ev_events
        int   ev_flags
        void *ev_arg
    
    char* event_get_version()

    int EV_TIMEOUT
    int EV_READ
    int EV_WRITE
    int EV_SIGNAL
    int EV_PERSIST

    int EVLIST_TIMEOUT
    int EVLIST_INSERTED
    int EVLIST_SIGNAL
    int EVLIST_ACTIVE
    int EVLIST_INTERNAL
    int EVLIST_INIT

    int DNS_ERR_NONE
    int DNS_ERR_FORMAT
    int DNS_ERR_SERVERFAILED
    int DNS_ERR_NOTEXIST
    int DNS_ERR_NOTIMPL
    int DNS_ERR_REFUSED
    int DNS_ERR_TRUNCATED
    int DNS_ERR_UNKNOWN
    int DNS_ERR_TIMEOUT
    int DNS_ERR_SHUTDOWN

    int DNS_IPv4_A
    int DNS_PTR
    int DNS_IPv6_AAAA

    int DNS_QUERY_NO_SEARCH

    void* event_base_new()
    int   event_reinit(void *base)
    int   event_base_dispatch(void*) nogil
    char* event_base_get_method(void*)
    void  event_base_free(void*)
    int   event_base_set(void *, event*)

    void event_set(event *ev, int fd, short event, event_handler handler, void *arg)
    int  event_add(event *ev, timeval *tv)
    int  event_del(event *ev)
    int  event_pending(event *ev, short, timeval *tv)
    void event_active(event *ev, int res, short ncalls)

    int EVLOOP_ONCE
    int EVLOOP_NONBLOCK
    char* _EVENT_VERSION
    
    struct evutil_addrinfo:
        int   ai_flags            # AI_PASSIVE, AI_CANONNAME, AI_NUMERICHOST
        int   ai_family           # PF_xxx
        int   ai_socktype         # SOCK_xxx
        int   ai_protocol         # 0 or IPPROTO_xxx for IPv4 and IPv6
        size_t ai_addrlen         # length of ai_addr
        char *ai_canonname        # canonical name for nodename
        void *ai_addr             # binary address
        evutil_addrinfo *ai_next  # next structure in linked list

    ctypedef void (*evdns_callback_type)(int result, char t, int count, int ttl, void *addrs, void *arg)
    ctypedef void (*evdns_getaddrinfo_cb)(int result, evutil_addrinfo *res, void *arg)

    void* evdns_base_new(void *event_base, int initialize_nameservers)

    void* current_base
    void evdns_base_free(void *dns_base, int fail_requests)
    char* evdns_err_to_string(int err)
    int evdns_base_nameserver_ip_add(void *dns_base, char *ip_as_string)
    int evdns_base_count_nameservers(void *base)
    void *evdns_base_resolve_ipv4(void *dns_base, char *name, int flags, evdns_callback_type callback, void *ptr)
    void *evdns_base_resolve_ipv6(void *dns_base, char *name, int flags, evdns_callback_type callback, void *ptr)
    void *evdns_base_resolve_reverse(void *dns_base, void *, int flags, evdns_callback_type callback, void *ptr)
    void *evdns_base_resolve_reverse_ipv6(void *dns_base, void *, int flags, evdns_callback_type callback, void *ptr)
    void  evdns_cancel_request(void *dns_base, void *req)
    int   evdns_base_set_option(void *dns_base, char *option, char *val)
    void* evdns_base_resolve_ipv4(void* base, char *name, int flags, evdns_callback_type callback, void *arg)
    void* evdns_base_resolve_ipv6(void* base, char *name, int flags, evdns_callback_type callback, void *arg)
    void* evdns_base_resolve_reverse(void* base, void *ip, int flags, evdns_callback_type callback, void *arg)
    void* evdns_base_resolve_reverse_ipv6(void* base, void *ip, int flags, evdns_callback_type callback, void *arg)

    void *evdns_getaddrinfo(void *dns_base, char *nodename, char *servname, evutil_addrinfo *hints_in, evdns_getaddrinfo_cb cb, void *arg)
    void evdns_getaddrinfo_cancel(void*)

    int EVUTIL_EAI_CANCEL
    int DNS_ERR_CANCEL
    int DNS_IPv4_A
    int DNS_IPv6_AAAA
    int DNS_PTR
