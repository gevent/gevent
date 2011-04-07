cdef extern from "ares.h":
    struct ares_options:
        void* sock_state_cb
        void* sock_state_cb_data

    int ARES_OPT_SOCK_STATE_CB
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


cdef extern from "inet_net_pton.h":
    int ares_inet_pton(int af, char *src, void *dst)
