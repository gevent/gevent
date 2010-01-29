__all__ += ['http_request', 'http_connection', 'http']

EVHTTP_REQUEST      = 0
EVHTTP_RESPONSE     = 1

EVHTTP_REQ_GET      = 0
EVHTTP_REQ_POST     = 1
EVHTTP_REQ_HEAD     = 2
EVHTTP_REQ_PUT      = 3
EVHTTP_REQ_DELETE   = 4

HTTP_method2name = { 0: 'GET', 1: 'POST', 2: 'HEAD', 3: 'PUT', 4: 'DELETE' }

cdef extern from *:
    ctypedef char* const_char_ptr "const char*"

cdef extern from "libevent.h":

    ctypedef unsigned short ev_uint16_t

    struct tailq_entry:
        void* tqe_next
    struct evkeyval:
        tailq_entry next
        char* key
        char* value
    struct evkeyvalq:
        pass
    evkeyval* TAILQ_FIRST(evkeyvalq* x)
    evkeyval* TAILQ_GET_NEXT(evkeyval* x)

    # evhttp.h:
    struct evhttp:
        pass
    struct evhttp_connection:
        pass
    struct evhttp_request:
        evhttp_connection* evcon
        evkeyvalq *input_headers
        evkeyvalq *output_headers
        char    *remote_host
        short   remote_port
        int kind
        int type
        char    *uri
        char    major
        char    minor
        int response_code
        char *response_code_line
        evbuffer *input_buffer
        int chunked
        evbuffer *output_buffer

    # evhttp
    ctypedef void (*evhttp_handler)(evhttp_request *, void *arg)

    evhttp*   evhttp_new(event_base *base)
    int       evhttp_bind_socket(evhttp *http, char* address, int port)
    int       evhttp_accept_socket(evhttp *http, int fd)
    void      evhttp_free(evhttp* http)
    int       EVHTTP_SET_CB(evhttp *http, char *uri,
                           evhttp_handler handler, void *arg)
    void      evhttp_set_gencb(evhttp *http,
                           evhttp_handler handler, void *arg)
    void      evhttp_del_cb(evhttp *http, char *uri)

    # request
    ctypedef void (*evhttp_request_cb)(evhttp_request *r, void *arg)

    evhttp_request *evhttp_request_new(evhttp_request_cb reqcb, void *arg)
    void            evhttp_request_free(evhttp_request *r)

    void      evhttp_send_reply(evhttp_request *req, int status, char* reason, evbuffer* buf)
    void      evhttp_send_reply_start(evhttp_request *req, int status, char *reason)
    void      evhttp_send_reply_chunk(evhttp_request *req, evbuffer *buf)
    void      evhttp_send_reply_end(evhttp_request *req)
    void      evhttp_send_error(evhttp_request *req, int error, char *reason)

    char*     evhttp_find_header(evkeyvalq*, char*)
    int       evhttp_remove_header(evkeyvalq*, char*)
    int       evhttp_add_header(evkeyvalq*, char*, char*)
    void      evhttp_clear_headers(evkeyvalq*)

    # connection
    ctypedef void (*conn_closecb)(evhttp_connection *c, void *arg)

    evhttp_connection   *evhttp_connection_new(char *addr, short port)
    void      evhttp_connection_free(evhttp_connection *c)
    void      evhttp_connection_set_local_address(evhttp_connection *c, char *addr)
    void      evhttp_connection_set_timeout(evhttp_connection *c, int secs)
    void      evhttp_connection_set_retries(evhttp_connection *c, int retry_max)
    void      evhttp_connection_set_closecb(evhttp_connection *c, conn_closecb closecb, void *arg)
    void      evhttp_connection_get_peer(evhttp_connection *evcon, char **address, ev_uint16_t *port)

    int       evhttp_make_request(evhttp_connection *c, evhttp_request *req, int cmd_type, char *uri)


class ObjectDeleted(AttributeError):
    pass

class HttpRequestDeleted(ObjectDeleted):
    """Raised when an attribute is accessed of http_request instance whose _obj is 0"""

class HttpConnectionDeleted(ObjectDeleted):
    """Raised when an attribute is accessed of http_connection instance whose _obj is 0"""


cdef class http_request:
    """Wrapper around libevent's :class:`evhttp_request` structure."""

    # It is possible to crash the process by using it directly.
    # prefer gevent.http and gevent.wsgi which should be safe

    cdef evhttp_request* __obj

    def __init__(self, size_t _obj):
        self.__obj = <evhttp_request*>_obj

    property _obj:

        def __get__(self):
            return <size_t>(self.__obj)

    def __nonzero__(self):
        if self.__obj:
            return True
        else:
            return False

    def detach(self):
        self.__obj = NULL

    def _format(self):
        args = (self.typestr, self.uri, self.major, self.minor,
                self.remote_host, self.remote_port)
        res = '"%s %s HTTP/%s.%s" %s:%s' % args
        if self.response_code:
            res += 'response=%s' % self.response_code
        if self.input_buffer:
            res += 'input=%s' % len(self.input_buffer)
        if self.output_buffer:
            res += 'output=%s' % len(self.output_buffer)
        return res

    def __str__(self):
        if self.__obj:
            return '<%s %s>' % (self.__class__.__name__, self._format())
        else:
            return '<%s deleted>' % self.__class__.__name__

    def __repr__(self):
        if self.__obj:
            return '<%s _obj=0x%x %s>' % (self.__class__.__name__, self._obj, self._format())
        else:
            return '<%s _obj=0x%x>' % (self.__class__.__name__, self._obj)

    def get_input_headers(self):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef evkeyvalq* headers = self.__obj.input_headers
        cdef evkeyval* p = TAILQ_FIRST(headers)
        cdef char *key, *value
        result = []
        while p:
            key = p.key
            value = p.value
            result.append((key if key else None, value if value else None))
            p = TAILQ_GET_NEXT(p)
        return result

    property connection:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return http_connection(<size_t>self.__obj.evcon)

    property remote_host:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            if self.__obj.remote_host:
                return self.__obj.remote_host

    property remote_port:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.remote_port

    property remote:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return (self.remote_host, self.remote_port)

    property kind:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.kind

    property type:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.type

    property typestr:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return HTTP_method2name.get(self.__obj.type) or str(self.__obj.type)

    property uri:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            if self.__obj.uri:
                return self.__obj.uri

    property major:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.major

    property minor:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.minor

    property version:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return (self.__obj.major, self.__obj.minor)

    property response_code:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.response_code

    property response_code_line:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            if self.__obj.response_code_line:
                return self.__obj.response_code_line

    property response:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return (self.response_code, self.response_code_line)

    property chunked:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.chunked

    property input_buffer:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return buffer(<size_t>self.__obj.input_buffer)

    property output_buffer:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return buffer(<size_t>self.__obj.output_buffer)

    def send_reply(self, int code, char *reason, object buf):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef evbuffer* c_buf
        if isinstance(buf, buffer):
            evhttp_send_reply(self.__obj, code, reason, (<buffer>buf).__obj)
        elif isinstance(buf, str):
            c_buf = evbuffer_new()
            evbuffer_add(c_buf, <char *>buf, len(buf))
            evhttp_send_reply(self.__obj, code, reason, c_buf)
            evbuffer_free(c_buf)
        else:
            raise TypeError('Expected str or buffer: %r' % (buf, ))

    def send_reply_start(self, int code, char *reason):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_send_reply_start(self.__obj, code, reason)

    def send_reply_chunk(self, object buf):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef evbuffer* c_buf
        if isinstance(buf, buffer):
            evhttp_send_reply_chunk(self.__obj, (<buffer>buf).__obj)
        elif isinstance(buf, str):
            c_buf = evbuffer_new()
            evbuffer_add(c_buf, <char *>buf, len(buf))
            evhttp_send_reply_chunk(self.__obj, c_buf)
            evbuffer_free(c_buf)
        else:
            raise TypeError('Expected str or buffer: %r' % (buf, ))

    def send_reply_end(self):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_send_reply_end(self.__obj)

    def send_error(self, int code, char* reason):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_send_error(self.__obj, code, reason)

    def find_input_header(self, char* key):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef const_char_ptr val = evhttp_find_header(self.__obj.input_headers, key)
        if val:
            return val

    def find_output_header(self, char* key):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef const_char_ptr val = evhttp_find_header(self.__obj.output_headers, key)
        if val:
            return val

    def add_input_header(self, char* key, char* value):
        if not self.__obj:
            raise HttpRequestDeleted
        if evhttp_add_header(self.__obj.input_headers, key, value):
            raise RuntimeError('Internal error in evhttp_add_header')

    def add_output_header(self, char* key, char* value):
        if not self.__obj:
            raise HttpRequestDeleted
        if evhttp_add_header(self.__obj.output_headers, key, value):
            raise RuntimeError('Internal error in evhttp_add_header')

    def remove_input_header(self, char* key):
        """Return True if header was found and removed"""
        if not self.__obj:
            raise HttpRequestDeleted
        return True if 0==evhttp_remove_header(self.__obj.input_headers, key) else False

    def remove_output_header(self, char* key):
        """Return True if header was found and removed"""
        if not self.__obj:
            raise HttpRequestDeleted
        return True if 0==evhttp_remove_header(self.__obj.output_headers, key) else False

    def clear_input_headers(self):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_clear_headers(self.__obj.input_headers)

    def clear_output_headers(self):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_clear_headers(self.__obj.output_headers)


cdef void _http_connection_closecb_handler(evhttp_connection* connection, void *arg) with gil:
    try:
        server = <object>arg
        conn = http_connection(<size_t>connection)
        server._cb_connection_close(conn)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for evhttp connection:\n  connection = %s\n server = %s\n\n' % (conn, server))
        except:
            pass


cdef class http_connection:

    cdef evhttp_connection* __obj

    def __init__(self, size_t _obj):
        self.__obj = <evhttp_connection*>_obj

    property _obj:

        def __get__(self):
            return <size_t>(self.__obj)

    def __nonzero__(self):
        if self.__obj:
            return True
        else:
            return False

    def __str__(self):
        if self.__obj:
            return '<%s %s>' % (self.__class__.__name__, self.peer)
        else:
            return '<%s deleted>' % (self.__class__.__name__)

    def __repr__(self):
        if self.__obj:
            return '<%s _obj=0x%x %s>' % (self.__class__.__name__, self._obj, self.peer)
        else:
            return '<%s _obj=0x%x>' % (self.__class__.__name__, self._obj)

    property peer:

        def __get__(self):
            if not self.__obj:
                raise HttpConnectionDeleted
            cdef char* address = NULL
            cdef ev_uint16_t port = 0
            evhttp_connection_get_peer(self.__obj, &address, &port)
            if address:
                addr = <str>address
            else:
                addr = None
            return (addr, port)

    def set_closecb(self, callback):
        if not self.__obj:
            raise HttpConnectionDeleted
        evhttp_connection_set_closecb(self.__obj, _http_connection_closecb_handler, <void *>callback)


cdef void _http_cb_handler(evhttp_request* request, void *arg) with gil:
    cdef object callback = <object>arg
    try:
        r = http_request(<size_t>request)
        callback(r)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for evhttp request:\n  request = %s\n callback = %s\n\n' % (r, callback))
        except:
            pass
        if request.response_code == 0:
            report_internal_error(request)


cdef void report_internal_error(evhttp_request* request):
    cdef evbuffer*  c_buf = evbuffer_new()
    evbuffer_add(c_buf, "<h1>Internal Server Error</h1>", 30)
    evhttp_send_reply(request, 500, "Internal Server Error", c_buf)
    evbuffer_free(c_buf)


cdef class http:
    cdef evhttp* __obj
    cdef object _gencb
    cdef list _cbs

    def __init__(self):
        self.__obj = evhttp_new(current_base)
        self._gencb = None
        self._cbs = []

    def __dealloc__(self):
        if self.__obj != NULL:
            evhttp_free(self.__obj)
        self.__obj = NULL

    property _obj:

        def __get__(self):
            return <size_t>(self.__obj)

    def __nonzero__(self):
        if self.__obj:
            return True
        else:
            return False

    def bind(self, char* address='127.0.0.1', int port=80):
        cdef int res = evhttp_bind_socket(self.__obj, address, port)
        if res:
            raise RuntimeError('Cannot bind %s:%s' % (address, port))

    def accept(self, int fd):
        cdef res = evhttp_accept_socket(self.__obj, fd)
        if res:
            raise RuntimeError("evhttp_accept_socket(%s) returned %s" % (fd, res))

    def start(cls, char* address='127.0.0.1', int port=80):
        #cdef evhttp* obj = evhttp_start(address, port)
        #if obj:
        #    return cls(<size_t>obj)
        raise RuntimeError('evhttp_start failed')

    def set_cb(self, char* path, object callback):
        cdef res = EVHTTP_SET_CB(self.__obj, path, _http_cb_handler, <void *>callback)
        if res == 0:
            self._cbs.append(callback)
            return
        elif res == -1:
            raise RuntimeError('evhttp_set_cb(%r, %r) returned %s: callback already exists' % (path, callback, res))
        else:
            raise RuntimeError('evhttp_set_cb(%r, %r) returned %s' % (path, callback, res))

    def set_gencb(self, callback):
        self._gencb = callback
        evhttp_set_gencb(self.__obj, _http_cb_handler, <void *>callback)

