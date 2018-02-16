# Copyright (c) 2011-2012 Denis Bilenko. See LICENSE for details.
# Automatic pickling of cdef classes was added in 0.26. Unfortunately it
# seems to be buggy (at least for the `result` class) and produces code that
# can't compile ("local variable 'result' referenced before assignment").
# See https://github.com/cython/cython/issues/1786
# cython: auto_pickle=False
cimport libcares as cares
import sys

from cpython.ref cimport Py_INCREF
from cpython.ref cimport Py_DECREF
from cpython.mem cimport PyMem_Malloc
from cpython.mem cimport PyMem_Free

from _socket import gaierror


__all__ = ['channel']

cdef object string_types
cdef object text_type

if sys.version_info[0] >= 3:
    string_types = str,
    text_type = str
else:
    string_types = __builtins__.basestring,
    text_type = __builtins__.unicode

TIMEOUT = 1

DEF EV_READ = 1
DEF EV_WRITE = 2


cdef extern from "dnshelper.c":
    int AF_INET
    int AF_INET6

    struct hostent:
        char* h_name
        int h_addrtype

    struct sockaddr_t "sockaddr":
        pass

    struct ares_channeldata:
        pass

    object parse_h_name(hostent*)
    object parse_h_aliases(hostent*)
    object parse_h_addr_list(hostent*)
    void* create_object_from_hostent(void*)

    # this imports _socket lazily
    object PyUnicode_FromString(char*)
    int PyTuple_Check(object)
    int PyArg_ParseTuple(object, char*, ...) except 0
    struct sockaddr_in6:
        pass
    int gevent_make_sockaddr(char* hostp, int port, int flowinfo, int scope_id, sockaddr_in6* sa6)


    void memset(void*, int, int)


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

ARES_FLAG_USEVC = cares.ARES_FLAG_USEVC
ARES_FLAG_PRIMARY = cares.ARES_FLAG_PRIMARY
ARES_FLAG_IGNTC = cares.ARES_FLAG_IGNTC
ARES_FLAG_NORECURSE = cares.ARES_FLAG_NORECURSE
ARES_FLAG_STAYOPEN = cares.ARES_FLAG_STAYOPEN
ARES_FLAG_NOSEARCH = cares.ARES_FLAG_NOSEARCH
ARES_FLAG_NOALIASES = cares.ARES_FLAG_NOALIASES
ARES_FLAG_NOCHECKRESP = cares.ARES_FLAG_NOCHECKRESP


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
    raise gaierror(-1, "Bad value for ai_flags: 0x%x" % flags)


cpdef strerror(code):
    return '%s: %s' % (_ares_errors.get(code) or code, cares.ares_strerror(code))


class InvalidIP(ValueError):
    pass


cdef void gevent_sock_state_callback(void *data, int s, int read, int write):
    if not data:
        return
    cdef channel ch = <channel>data
    ch._sock_state_callback(s, read, write)


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
        # add repr_recursive precaution

    def successful(self):
        return self.exception is None

    def get(self):
        if self.exception is not None:
            raise self.exception
        return self.value


class ares_host_result(tuple):

    def __new__(cls, family, iterable):
        cdef object self = tuple.__new__(cls, iterable)
        self.family = family
        return self

    def __getnewargs__(self):
        return (self.family, tuple(self))


cdef void gevent_ares_host_callback(void *arg, int status, int timeouts, hostent* host):
    cdef channel channel
    cdef object callback
    channel, callback = <tuple>arg
    Py_DECREF(<tuple>arg)
    cdef object host_result
    try:
        if status or not host:
            callback(result(None, gaierror(status, strerror(status))))
        else:
            try:
                host_result = ares_host_result(host.h_addrtype, (parse_h_name(host), parse_h_aliases(host), parse_h_addr_list(host)))
            except:
                callback(result(None, sys.exc_info()[1]))
            else:
                callback(result(host_result))
    except:
        channel.loop.handle_error(callback, *sys.exc_info())


cdef void gevent_ares_nameinfo_callback(void *arg, int status, int timeouts, char *c_node, char *c_service):
    cdef channel channel
    cdef object callback
    channel, callback = <tuple>arg
    Py_DECREF(<tuple>arg)
    cdef object node
    cdef object service
    try:
        if status:
            callback(result(None, gaierror(status, strerror(status))))
        else:
            if c_node:
                node = PyUnicode_FromString(c_node)
            else:
                node = None
            if c_service:
                service = PyUnicode_FromString(c_service)
            else:
                service = None
            callback(result((node, service)))
    except:
        channel.loop.handle_error(callback, *sys.exc_info())


cdef class channel:

    cdef public object loop
    cdef ares_channeldata* channel
    cdef public dict _watchers
    cdef public object _timer

    def __init__(self, object loop, flags=None, timeout=None, tries=None, ndots=None,
                 udp_port=None, tcp_port=None, servers=None):
        cdef ares_channeldata* channel = NULL
        cdef cares.ares_options options
        memset(&options, 0, sizeof(cares.ares_options))
        cdef int optmask = cares.ARES_OPT_SOCK_STATE_CB
        options.sock_state_cb = <void*>gevent_sock_state_callback
        options.sock_state_cb_data = <void*>self
        if flags is not None:
            options.flags = int(flags)
            optmask |= cares.ARES_OPT_FLAGS
        if timeout is not None:
            options.timeout = int(float(timeout) * 1000)
            optmask |= cares.ARES_OPT_TIMEOUTMS
        if tries is not None:
            options.tries = int(tries)
            optmask |= cares.ARES_OPT_TRIES
        if ndots is not None:
            options.ndots = int(ndots)
            optmask |= cares.ARES_OPT_NDOTS
        if udp_port is not None:
            options.udp_port = int(udp_port)
            optmask |= cares.ARES_OPT_UDP_PORT
        if tcp_port is not None:
            options.tcp_port = int(tcp_port)
            optmask |= cares.ARES_OPT_TCP_PORT
        cdef int result = cares.ares_library_init(cares.ARES_LIB_INIT_ALL)  # ARES_LIB_INIT_WIN32 -DUSE_WINSOCK?
        if result:
            raise gaierror(result, strerror(result))
        result = cares.ares_init_options(&channel, &options, optmask)
        if result:
            raise gaierror(result, strerror(result))
        self._timer = loop.timer(TIMEOUT, TIMEOUT)
        self._watchers = {}
        self.channel = channel
        try:
            if servers is not None:
                self.set_servers(servers)
            self.loop = loop
        except:
            self.destroy()
            raise

    def __repr__(self):
        args = (self.__class__.__name__, id(self), self._timer, len(self._watchers))
        return '<%s at 0x%x _timer=%r _watchers[%s]>' % args

    def destroy(self):
        if self.channel:
            # XXX ares_library_cleanup?
            cares.ares_destroy(self.channel)
            self.channel = NULL
            self._watchers.clear()
            self._timer.stop()
            self.loop = None

    def __dealloc__(self):
        if self.channel:
            # XXX ares_library_cleanup?
            cares.ares_destroy(self.channel)
            self.channel = NULL

    cpdef set_servers(self, servers=None):
        if not self.channel:
            raise gaierror(cares.ARES_EDESTRUCTION, 'this ares channel has been destroyed')
        if not servers:
            servers = []
        if isinstance(servers, string_types):
            servers = servers.split(',')
        cdef int length = len(servers)
        cdef int result, index
        cdef char* string
        cdef cares.ares_addr_node* c_servers
        if length <= 0:
            result = cares.ares_set_servers(self.channel, NULL)
        else:
            c_servers = <cares.ares_addr_node*>PyMem_Malloc(sizeof(cares.ares_addr_node) * length)
            if not c_servers:
                raise MemoryError
            try:
                index = 0
                for server in servers:
                    if isinstance(server, unicode):
                        server = server.encode('ascii')
                    string = <char*?>server
                    if cares.ares_inet_pton(AF_INET, string, &c_servers[index].addr) > 0:
                        c_servers[index].family = AF_INET
                    elif cares.ares_inet_pton(AF_INET6, string, &c_servers[index].addr) > 0:
                        c_servers[index].family = AF_INET6
                    else:
                        raise InvalidIP(repr(string))
                    c_servers[index].next = &c_servers[index] + 1
                    index += 1
                    if index >= length:
                        break
                c_servers[length - 1].next = NULL
                index = cares.ares_set_servers(self.channel, c_servers)
                if index:
                    raise ValueError(strerror(index))
            finally:
                PyMem_Free(c_servers)

    # this crashes c-ares
    #def cancel(self):
    #    cares.ares_cancel(self.channel)

    cdef _sock_state_callback(self, int socket, int read, int write):
        if not self.channel:
            return
        cdef object watcher = self._watchers.get(socket)
        cdef int events = 0
        if read:
            events |= EV_READ
        if write:
            events |= EV_WRITE
        if watcher is None:
            if not events:
                return
            watcher = self.loop.io(socket, events)
            self._watchers[socket] = watcher
        elif events:
            if watcher.events == events:
                return
            watcher.stop()
            watcher.events = events
        else:
            watcher.stop()
            watcher.close()
            self._watchers.pop(socket, None)
            if not self._watchers:
                self._timer.stop()
            return
        watcher.start(self._process_fd, watcher, pass_events=True)
        self._timer.again(self._on_timer)

    def _on_timer(self):
        cares.ares_process_fd(self.channel, cares.ARES_SOCKET_BAD, cares.ARES_SOCKET_BAD)

    def _process_fd(self, int events, object watcher):
        if not self.channel:
            return
        cdef int read_fd = watcher.fd
        cdef int write_fd = read_fd
        if not (events & EV_READ):
            read_fd = cares.ARES_SOCKET_BAD
        if not (events & EV_WRITE):
            write_fd = cares.ARES_SOCKET_BAD
        cares.ares_process_fd(self.channel, read_fd, write_fd)

    def gethostbyname(self, object callback, char* name, int family=AF_INET):
        if not self.channel:
            raise gaierror(cares.ARES_EDESTRUCTION, 'this ares channel has been destroyed')
        # note that for file lookups still AF_INET can be returned for AF_INET6 request
        cdef object arg = (self, callback)
        Py_INCREF(arg)
        cares.ares_gethostbyname(self.channel, name, family, <void*>gevent_ares_host_callback, <void*>arg)

    def gethostbyaddr(self, object callback, char* addr):
        if not self.channel:
            raise gaierror(cares.ARES_EDESTRUCTION, 'this ares channel has been destroyed')
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
            raise InvalidIP(repr(addr))
        cdef object arg = (self, callback)
        Py_INCREF(arg)
        cares.ares_gethostbyaddr(self.channel, addr_packed, length, family, <void*>gevent_ares_host_callback, <void*>arg)

    cpdef _getnameinfo(self, object callback, tuple sockaddr, int flags):
        if not self.channel:
            raise gaierror(cares.ARES_EDESTRUCTION, 'this ares channel has been destroyed')
        cdef char* hostp = NULL
        cdef int port = 0
        cdef int flowinfo = 0
        cdef int scope_id = 0
        cdef sockaddr_in6 sa6
        if not PyTuple_Check(sockaddr):
            raise TypeError('expected a tuple, got %r' % (sockaddr, ))
        PyArg_ParseTuple(sockaddr, "si|ii", &hostp, &port, &flowinfo, &scope_id)
        if port < 0 or port > 65535:
            raise gaierror(-8, 'Invalid value for port: %r' % port)
        cdef int length = gevent_make_sockaddr(hostp, port, flowinfo, scope_id, &sa6)
        if length <= 0:
            raise InvalidIP(repr(hostp))
        cdef object arg = (self, callback)
        Py_INCREF(arg)
        cdef sockaddr_t* x = <sockaddr_t*>&sa6
        cares.ares_getnameinfo(self.channel, x, length, flags, <void*>gevent_ares_nameinfo_callback, <void*>arg)

    def getnameinfo(self, object callback, tuple sockaddr, int flags):
        try:
            flags = _convert_cares_flags(flags)
        except gaierror:
            # The stdlib just ignores bad flags
            flags = 0
        return self._getnameinfo(callback, sockaddr, flags)
