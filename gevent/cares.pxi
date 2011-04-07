cimport cares
import sys


cdef extern from "dnshelper.c":
    int AF_INET
    int AF_INET6

    struct hostent:
        char* h_name
        int h_addrtype

    object parse_h_aliases(hostent*)
    object parse_h_addr_list(hostent*)
    void* create_object_from_hostent(void*)

    # this imports _socket lazily
    object get_socket_error()
    object get_socket_gaierror()
    object PyString_FromString(char*)
    int PyTuple_Check(object)
    int PyArg_ParseTuple(object, char*, ...) except 0
    struct sockaddr_in6:
        pass
    int gevent_make_sockaddr(char* hostp, int port, int flowinfo, int scope_id, sockaddr_in6* sa6)

cdef extern from "callbacks.h":
    void gevent_handle_error(void* loop, void* callback)


ARES_SUCCESS = cares.ARES_SUCCESS
ARES_ENODATA = cares.ARES_ENODATA
ARES_EFORMERR = cares.ARES_EFORMERR
ARES_ESERVFAIL = cares.ARES_ESERVFAIL
ARES_ENOTFOUND = cares.ARES_ENOTFOUND
ARES_ENOTIMP = cares.ARES_ENOTIMP
ARES_EREFUSED = cares.ARES_EREFUSED
ARES_EBADQUERY = cares.ARES_EBADQUERY
ARES_EBADNAME = cares.ARES_EBADNAME
ARES_EBADFAMILY = cares.ARES_EBADFAMILY
ARES_EBADRESP = cares.ARES_EBADRESP
ARES_ECONNREFUSED = cares.ARES_ECONNREFUSED
ARES_ETIMEOUT = cares.ARES_ETIMEOUT
ARES_EOF = cares.ARES_EOF
ARES_EFILE = cares.ARES_EFILE
ARES_ENOMEM = cares.ARES_ENOMEM
ARES_EDESTRUCTION = cares.ARES_EDESTRUCTION
ARES_EBADSTR = cares.ARES_EBADSTR
ARES_EBADFLAGS = cares.ARES_EBADFLAGS
ARES_ENONAME = cares.ARES_ENONAME
ARES_EBADHINTS = cares.ARES_EBADHINTS
ARES_ENOTINITIALIZED = cares.ARES_ENOTINITIALIZED
ARES_ELOADIPHLPAPI = cares.ARES_ELOADIPHLPAPI
ARES_EADDRGETNETWORKPARAMS = cares.ARES_EADDRGETNETWORKPARAMS
ARES_ECANCELLED = cares.ARES_ECANCELLED


_ares_errors = dict([
                (cares.ARES_SUCCESS, 'ARES_SUCCESS'),
                (cares.ARES_ENODATA, 'ARES_ENODATA'),
                (cares.ARES_EFORMERR, 'ARES_EFORMERR'),
                (cares.ARES_ESERVFAIL, 'ARES_ESERVFAIL'),
                (cares.ARES_ENOTFOUND, 'ARES_ENOTFOUND'),
                (cares.ARES_ENOTIMP, 'ARES_ENOTIMP'),
                (cares.ARES_EREFUSED, 'ARES_EREFUSED'),
                (cares.ARES_EBADQUERY, 'ARES_EBADQUERY'),
                (cares.ARES_EBADNAME, 'ARES_EBADNAME'),
                (cares.ARES_EBADFAMILY, 'ARES_EBADFAMILY'),
                (cares.ARES_EBADRESP, 'ARES_EBADRESP'),
                (cares.ARES_ECONNREFUSED, 'ARES_ECONNREFUSED'),
                (cares.ARES_ETIMEOUT, 'ARES_ETIMEOUT'),
                (cares.ARES_EOF, 'ARES_EOF'),
                (cares.ARES_EFILE, 'ARES_EFILE'),
                (cares.ARES_ENOMEM, 'ARES_ENOMEM'),
                (cares.ARES_EDESTRUCTION, 'ARES_EDESTRUCTION'),
                (cares.ARES_EBADSTR, 'ARES_EBADSTR'),
                (cares.ARES_EBADFLAGS, 'ARES_EBADFLAGS'),
                (cares.ARES_ENONAME, 'ARES_ENONAME'),
                (cares.ARES_EBADHINTS, 'ARES_EBADHINTS'),
                (cares.ARES_ENOTINITIALIZED, 'ARES_ENOTINITIALIZED'),
                (cares.ARES_ELOADIPHLPAPI, 'ARES_ELOADIPHLPAPI'),
                (cares.ARES_EADDRGETNETWORKPARAMS, 'ARES_EADDRGETNETWORKPARAMS'),
                (cares.ARES_ECANCELLED, 'ARES_ECANCELLED')])


# maps c-ares flag to _socket module flag
_cares_flag_map = None


cdef _prepare_cares_flag_map():
    global _cares_flag_map
    import _socket
    _cares_flag_map = [
        (getattr(_socket, 'NI_NUMERICHOST', 1), cares.ARES_NI_NUMERICHOST),
        (getattr(_socket, 'NI_NUMERICSERV', 2), cares.ARES_NI_NUMERICSERV),
        (getattr(_socket, 'NI_NOFQDN', 4), cares.ARES_NI_NOFQDN),
        (getattr(_socket, 'NI_NAMEREQD', 8), cares.ARES_NI_NAMEREQD),
        (getattr(_socket, 'NI_DGRAM', 16), cares.ARES_NI_DGRAM)]


cpdef _convert_cares_flags(int flags, int default=cares.ARES_NI_LOOKUPHOST|cares.ARES_NI_LOOKUPSERVICE):
    if _cares_flag_map is None:
        _prepare_cares_flag_map()
    for socket_flag, cares_flag in _cares_flag_map:
        if socket_flag & flags:
            default |= cares_flag
            flags &= ~socket_flag
        if not flags:
            return default
    raise get_socket_gaierror()(-1, "Bad value for ai_flags: 0x%x" % flags)


def _ares_strerror(code):
    return cares.ares_strerror(code)


cpdef ares_strerror(code):
    return '%s: %s' % (_ares_errors.get(code) or code, cares.ares_strerror(code))


cdef void gevent_sock_state_callback(void *data, int s, int read, int write):
    if not data:
        return
    cdef ares_channel channel = <ares_channel>data
    channel._sock_state_callback(s, read, write)


cdef class result:
    cdef public object value
    cdef public object exception

    def __init__(self, object value=None, object exception=None):
        self.value = value
        self.exception = exception

    def __repr__(self):
        if self.exception is None:
            return '%s(%r)' % (self.__class__.__name__, self.value)
        elif self.value is None:
            return '%s(exception=%r)' % (self.__class__.__name__, self.exception)
        else:
            return '%s(value=%r, exception=%r)' % (self.__class__.__name__, self.value, self.exception)

    def successful(self):
        return self.exception is None

    def get(self):
        if self.exception is not None:
            raise self.exception
        return self.value


class ares_host_result(tuple):

    def __new__(cls, family, *args):
        cdef object self = tuple.__new__(cls, *args)
        self.family = family
        return self


cdef void gevent_ares_host_callback(void *arg, int status, int timeouts, hostent* host):
    cdef object loop, callback
    loop, callback = <tuple>arg
    Py_DECREF(arg)
    cdef object host_result
    try:
        if status or not host:
            callback(result(None, get_socket_gaierror()(status, ares_strerror(status))))
        else:
            try:
                host_result = ares_host_result(host.h_addrtype, (host.h_name, parse_h_aliases(host), parse_h_addr_list(host)))
            except:
                callback(result(None, sys.exc_info()[1]))
            else:
                callback(result(host_result))
    except:
        gevent_handle_error(<void*>loop, <void*>callback)


cdef void gevent_ares_nameinfo_callback(void *arg, int status, int timeouts, char *c_node, char *c_service):
    cdef object loop, callback
    loop, callback = <tuple>arg
    Py_DECREF(arg)
    cdef object node
    cdef object service
    try:
        if status:
            callback(result(None, get_socket_gaierror()(status, ares_strerror(status))))
        else:
            if c_node:
                node = PyString_FromString(c_node)
            else:
                node = None
            if c_service:
                service = PyString_FromString(c_service)
            else:
                service = None
            callback(result((node, service)))
    except:
        gevent_handle_error(<void*>loop, <void*>callback)


cdef public class ares_channel [object PyGeventAresChannelObject, type PyGeventAresChannel_Type]:

    cdef public loop loop
    cdef void* channel
    cdef public dict _watchers

    def __init__(self, loop loop):
        cdef int result = cares.ares_library_init(cares.ARES_LIB_INIT_ALL)
        if result:
            raise get_socket_gaierror()(result, ares_strerror(result))
        cdef cares.ares_options options
        options.sock_state_cb = <void*>gevent_sock_state_callback
        options.sock_state_cb_data = <void*>self
        result = cares.ares_init_options(&self.channel, &options, cares.ARES_OPT_SOCK_STATE_CB)
        if result:
            raise get_socket_gaierror()(result, ares_strerror(result))
        self.loop = loop
        self._watchers = {}

    def __dealloc__(self):
        if self.channel:
            cares.ares_destroy(self.channel)
            self.channel = NULL

    # this crashes c-ares
    #def cancel(self):
    #    cares.ares_cancel(self.channel)

    cdef _sock_state_callback(self, int socket, int read, int write):
        cdef io watcher = self._watchers.get(socket)
        cdef int events = 0
        if read:
            events |= libev.EV_READ
        if write:
            events |= libev.EV_WRITE
        if watcher is None:
            if not events:
                return
            watcher = self.loop.io(socket, events)
            self._watchers[socket] = watcher
        elif events:
            if watcher._watcher.events != events:
                watcher.stop()
                watcher._watcher.events = events
        else:
            self._watchers.pop(socket, None)
            return
        watcher._start(self._process_fd, (GEVENT_CORE_EVENTS, watcher))

    def _process_fd(self, int events, io watcher):
        #print '_process_fd', watcher, events
        cdef int read_fd = watcher._watcher.fd
        cdef int write_fd = read_fd
        if not (events & libev.EV_READ):
            read_fd = cares.ARES_SOCKET_BAD
        if not (events & libev.EV_WRITE):
            write_fd = cares.ARES_SOCKET_BAD
        cares.ares_process_fd(self.channel, read_fd, write_fd)

    def gethostbyname(self, object callback, char* name, int family=AF_INET):
        # if family == AF_INET, send request for AF_INET
        # if family == AF_UNSPEC, send request for AF_INET6 for AF_INET6 then for AF_INET if the former fails
        # if family == AF_INET6, the bundled c-ares sends requests for AF_INET6 only whereas the stock c-ares
        #                        behaves the same as AS_UNSPEC
        # note that for file lookups still AF_INET can be returned for AF_INET6 request
        cdef object arg = (self.loop, callback)
        Py_INCREF(<void*>arg)
        cares.ares_gethostbyname(self.channel, name, family, <void*>gevent_ares_host_callback, <void*>arg)

    def gethostbyaddr(self, object callback, char* addr):
        # will guess the family
        cdef char addr_packed[16]
        cdef int family
        cdef int length
        if cares.ares_inet_pton(AF_INET, addr, addr_packed) > 0:
            family = AF_INET
            length = 4
        elif cares.ares_inet_pton(AF_INET6, addr, addr_packed) > 0:
            family = AF_INET6
            length = 16
        else:
            callback(result(exception=ValueError('illegal IP address string: %r' % addr)))
            return
        cdef object arg = (self.loop, callback)
        Py_INCREF(<void*>arg)
        cares.ares_gethostbyaddr(self.channel, addr_packed, length, family, <void*>gevent_ares_host_callback, <void*>arg)

    cpdef _getnameinfo(self, object callback, tuple sockaddr, int flags):
        cdef char* hostp
        cdef int port = 0
        cdef int flowinfo = 0
        cdef int scope_id = 0
        cdef sockaddr_in6 sa6
        cdef object exc_type
        if not PyTuple_Check(sockaddr):
            raise TypeError('expected a tuple, got %r' % (sockaddr, ))
        PyArg_ParseTuple(sockaddr, "si|ii", &hostp, &port, &flowinfo, &scope_id)
        if port < 0 or port > 65535:
            raise get_socket_gaierror()('invalid value for port: %r' % port)
        cdef int length = gevent_make_sockaddr(hostp, port, flowinfo, scope_id, &sa6)
        if length <= 0:
            callback(result(exception=ValueError('illegal IP address string: %r' % hostp)))
            return
        cdef object arg = (self.loop, callback)
        Py_INCREF(<void*>arg)
        cares.ares_getnameinfo(self.channel, &sa6, length, flags, <void*>gevent_ares_nameinfo_callback, <void*>arg)

    def getnameinfo(self, object callback, tuple sockaddr, int flags):
        return self._getnameinfo(callback, sockaddr, _convert_cares_flags(flags))

# XXX add timeouts
