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
    int       EVHTTP_SET_CB(evhttp *http, char *uri, evhttp_handler handler, void *arg)
    void      evhttp_set_gencb(evhttp *http, evhttp_handler handler, void *arg)
    void      evhttp_del_cb(evhttp *http, char *uri)

    # request
    ctypedef void (*evhttp_request_cb)(evhttp_request *r, void *arg)

    evhttp_request *evhttp_request_new(evhttp_request_cb reqcb, void *arg)
    void      evhttp_request_free(evhttp_request *r)

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

    cdef object __weakref__
    cdef evhttp_request* __obj
    cdef object _input_buffer
    cdef object _output_buffer
    cdef public object default_response_headers

    def __init__(self, size_t _obj, object default_response_headers):
        self.__obj = <evhttp_request*>_obj
        self.default_response_headers = default_response_headers

    def __dealloc__(self):
        cdef evhttp_request* obj = self.__obj
        if obj != NULL:
            self.__obj = NULL
            report_internal_error(obj)

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
        if self._input_buffer is not None:
            self._input_buffer.detach()
        if self._output_buffer is not None:
            self._output_buffer.detach()

    def _format(self):
        args = (self.typestr, self.uri, self.major, self.minor,
                self.remote_host, self.remote_port)
        res = '"%s %s HTTP/%s.%s" %s:%s' % args
        if self.response_code:
            res += ' response=%s' % self.response_code
        if self.input_buffer:
            res += ' input=%s' % len(self.input_buffer)
        if self.output_buffer:
            res += ' output=%s' % len(self.output_buffer)
        return res

    def __str__(self):
        try:
            info = self._format()
        except HttpRequestDeleted:
            info = 'deleted'
        except Exception, ex:
            info = str(ex) or repr(ex) or '<Error>'
        return '<%s %s>' % (self.__class__.__name__, info)

    def __repr__(self):
        try:
            info = ' ' + self._format()
        except HttpRequestDeleted:
            info = ''
        except Exception, ex:
            info = ' ' + (str(ex) or repr(ex) or '<Error>')
        return '<%s _obj=0x%x %s>' % (self.__class__.__name__, self._obj, info)

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
            return (self.response_code, self.response_code_line)

    property chunked:

        def __get__(self):
            if not self.__obj:
                raise HttpRequestDeleted
            return self.__obj.chunked

    property input_buffer:

        def __get__(self):
            if self._input_buffer is not None:
                return self._input_buffer
            if not self.__obj:
                raise HttpRequestDeleted
            self._input_buffer = buffer(<size_t>self.__obj.input_buffer)
            return self._input_buffer

    property output_buffer:

        def __get__(self):
            if self._output_buffer is not None:
                return self._output_buffer
            if not self.__obj:
                raise HttpRequestDeleted
            self._output_buffer = buffer(<size_t>self.__obj.output_buffer)
            return self._output_buffer

    def _add_default_response_headers(self):
        for key, value in self.default_response_headers:
            if not self.find_output_header(key):
                self.add_output_header(key, value)

    def send_reply(self, int code, char *reason, object buf):
        if not self.__obj:
            raise HttpRequestDeleted
        cdef evbuffer* c_buf
        if isinstance(buf, buffer):
            self._add_default_response_headers()
            evhttp_send_reply(self.__obj, code, reason, (<buffer>buf).__obj)
        elif isinstance(buf, str):
            self._add_default_response_headers()
            c_buf = evbuffer_new()
            evbuffer_add(c_buf, <char *>buf, len(buf))
            evhttp_send_reply(self.__obj, code, reason, c_buf)
            evbuffer_free(c_buf)
        else:
            raise TypeError('Expected str or buffer: %r' % (buf, ))

    def send_reply_start(self, int code, char *reason):
        if not self.__obj:
            raise HttpRequestDeleted
        self._add_default_response_headers()
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
        self._add_default_response_headers()
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
        return True if 0 == evhttp_remove_header(self.__obj.input_headers, key) else False

    def remove_output_header(self, char* key):
        """Return True if header was found and removed"""
        if not self.__obj:
            raise HttpRequestDeleted
        return True if 0 == evhttp_remove_header(self.__obj.output_headers, key) else False

    def clear_input_headers(self):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_clear_headers(self.__obj.input_headers)

    def clear_output_headers(self):
        if not self.__obj:
            raise HttpRequestDeleted
        evhttp_clear_headers(self.__obj.output_headers)


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
        try:
            peer = self.peer
        except HttpConnectionDeleted:
            peer = 'deleted'
        return '<%s %s>' % (self.__class__.__name__, peer)

    def __repr__(self):
        try:
            peer = ' %s' % (self.peer, )
        except HttpConnectionDeleted:
            peer = ''
        return '<%s _obj=0x%x%s>' % (self.__class__.__name__, self._obj, peer)

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


cdef void _http_cb_handler(evhttp_request* request, void *arg) with gil:
    cdef http server = <object>arg
    cdef http_request req = http_request(<size_t>request, server.default_response_headers)
    cdef evhttp_connection* conn = request.evcon
    cdef object requests
    try:
        evhttp_connection_set_closecb(conn, _http_closecb_handler, arg)
        requests = server._requests.pop(<size_t>conn, None)
        if requests is None:
            requests = weakref.WeakKeyDictionary()
            server._requests[<size_t>conn] = requests
        requests[req] = True
        server.handle(req)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('%s: Failed to handle request: %s\n\n' % (server, req, ))
        except:
            traceback.print_exc()
        # without clearing exc_info a reference to the request is somehow leaked
        sys.exc_clear()


cdef void _http_closecb_handler(evhttp_connection* connection, void *arg) with gil:
    cdef http server = <object>arg
    cdef object requests
    for request in server._requests.pop(<size_t>connection, {}).keys():
        request.detach()


cdef void _http_cb_reply_error(evhttp_request* request, void *arg):
    report_internal_error(request)


cdef void report_internal_error(evhttp_request* request):
    cdef evbuffer* c_buf
    if request != NULL and request.response_code == 0:
        evhttp_add_header(request.output_headers, "Connection", "close")
        evhttp_add_header(request.output_headers, "Content-type", "text/plain")
        c_buf = evbuffer_new()
        evhttp_add_header(request.output_headers, "Content-length", "21")
        evbuffer_add(c_buf, "Internal Server Error", 21)
        evhttp_send_reply(request, 500, "Internal Server Error", c_buf)
        evbuffer_free(c_buf)


cdef class http:
    cdef evhttp* __obj
    cdef public object handle
    cdef public object default_response_headers
    cdef dict _requests

    def __init__(self, object handle, object default_response_headers=None):
        self.handle = handle
        if default_response_headers is None:
            self.default_response_headers = []
        else:
            self.default_response_headers = default_response_headers
        self._requests = {} # maps connection id to WeakKeyDictionary which holds requests
        self.__obj = evhttp_new(current_base)
        evhttp_set_gencb(self.__obj, _http_cb_handler, <void *>self)

    def __dealloc__(self):
        if self.__obj != NULL:
            evhttp_set_gencb(self.__obj, _http_cb_reply_error, NULL)
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
            raise RuntimeError('evhttp_bind_socket(%r, %r) returned %r' % (address, port, res))

    def accept(self, int fd):
        cdef res = evhttp_accept_socket(self.__obj, fd)
        if res:
            raise RuntimeError("evhttp_accept_socket(%r) returned %r" % (fd, res))

