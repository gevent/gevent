cdef extern from "ares.h":
    struct ares_options:
        int flags
        void* sock_state_cb
        void* sock_state_cb_data
        int timeout
        int tries
        int ndots
        unsigned short udp_port
        unsigned short tcp_port
        char **domains
        int ndomains
        char* lookups

    int ARES_OPT_FLAGS
    int ARES_OPT_SOCK_STATE_CB
    int ARES_OPT_TIMEOUTMS
    int ARES_OPT_TRIES
    int ARES_OPT_NDOTS
    int ARES_OPT_TCP_PORT
    int ARES_OPT_UDP_PORT
    int ARES_OPT_SERVERS
    int ARES_OPT_DOMAINS
    int ARES_OPT_LOOKUPS

    int ARES_FLAG_USEVC
    int ARES_FLAG_PRIMARY
    int ARES_FLAG_IGNTC
    int ARES_FLAG_NORECURSE
    int ARES_FLAG_STAYOPEN
    int ARES_FLAG_NOSEARCH
    int ARES_FLAG_NOALIASES
    int ARES_FLAG_NOCHECKRESP

    int ARES_LIB_INIT_ALL
    int ARES_SOCKET_BAD

    int ARES_SUCCESS
    int ARES_ENODATA
    int ARES_EFORMERR
    int ARES_ESERVFAIL
    int ARES_ENOTFOUND
    int ARES_ENOTIMP
    int ARES_EREFUSED
    int ARES_EBADQUERY
    int ARES_EBADNAME
    int ARES_EBADFAMILY
    int ARES_EBADRESP
    int ARES_ECONNREFUSED
    int ARES_ETIMEOUT
    int ARES_EOF
    int ARES_EFILE
    int ARES_ENOMEM
    int ARES_EDESTRUCTION
    int ARES_EBADSTR
    int ARES_EBADFLAGS
    int ARES_ENONAME
    int ARES_EBADHINTS
    int ARES_ENOTINITIALIZED
    int ARES_ELOADIPHLPAPI
    int ARES_EADDRGETNETWORKPARAMS
    int ARES_ECANCELLED

    int ARES_NI_NOFQDN
    int ARES_NI_NUMERICHOST
    int ARES_NI_NAMEREQD
    int ARES_NI_NUMERICSERV
    int ARES_NI_DGRAM
    int ARES_NI_TCP
    int ARES_NI_UDP
    int ARES_NI_SCTP
    int ARES_NI_DCCP
    int ARES_NI_NUMERICSCOPE
    int ARES_NI_LOOKUPHOST
    int ARES_NI_LOOKUPSERVICE


    int ares_library_init(int flags)
    void ares_library_cleanup()
    int ares_init_options(void *channelptr, ares_options *options, int)
    int ares_init(void *channelptr)
    void ares_destroy(void *channelptr)
    void ares_gethostbyname(void* channel, char *name, int family, void* callback, void *arg)
    void ares_gethostbyaddr(void* channel, void *addr, int addrlen, int family, void* callback, void *arg)
    void ares_process_fd(void* channel, int read_fd, int write_fd)
    char* ares_strerror(int code)
    void ares_cancel(void* channel)
    void ares_getnameinfo(void* channel, void* sa, int salen, int flags, void* callback, void *arg)

    struct in_addr:
        pass

    struct ares_in6_addr:
        pass

    struct addr_union:
        in_addr addr4
        ares_in6_addr addr6

    struct ares_addr_node:
        ares_addr_node *next
        int family
        addr_union addr

    int ares_set_servers(void* channel, ares_addr_node *servers)


cdef extern from "cares_pton.h":
    int ares_inet_pton(int af, char *src, void *dst)
