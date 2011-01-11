__all__ += ['buffer']

cdef extern from "string.h":
    void *memchr(void *s, int c, size_t n)

cdef extern from "libevent.h":
    struct evbuffer:
        char *buf "buffer"
        int off

    evbuffer *evbuffer_new()
    int       evbuffer_add(evbuffer *buf, char *p, int len)
    char     *evbuffer_readline(evbuffer *buf)
    void      evbuffer_free(evbuffer *buf)
    size_t    evbuffer_get_length(evbuffer *buffer)
    unsigned char *EVBUFFER_PULLUP(evbuffer *buf, size_t size)
    int       EVBUFFER_DRAIN(evbuffer *buf, size_t len)


cdef class buffer:
    """file-like wrapper for libevent's :class:`evbuffer` structure.

    Note, that the wrapper does not own the structure, libevent does.
    """
    cdef evbuffer* __obj

    def __init__(self, size_t _obj):
        self.__obj = <evbuffer*>_obj

    property _obj:

        def __get__(self):
            return <size_t>(self.__obj)

    def __len__(self):
        if self.__obj:
            return evbuffer_get_length(self.__obj)
        else:
            return 0

    def __nonzero__(self):
        if self.__obj:
            return evbuffer_get_length(self.__obj)

    def detach(self):
        self.__obj = NULL

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def read(self, long size=-1):
        """Drain the first *size* bytes from the buffer (or what's left if there are less than *size* bytes).

        If *size* is negative, drain the whole buffer.
        """
        if not self.__obj:
            return ''
        cdef long length = evbuffer_get_length(self.__obj)
        if size < 0:
            size = length
        else:
            size = min(size, length)
        if size <= 0:
            return ''
        cdef char* data = <char*>EVBUFFER_PULLUP(self.__obj, size)
        if not data:
            return ''
        cdef object result = PyString_FromStringAndSize(data, size)
        cdef int res = EVBUFFER_DRAIN(self.__obj, size)
        if res:
            try:
                sys.stderr.write('evbuffer_drain(0x%x, %s) returned %s\n' % (self._obj, size, res))
            except:
                traceback.print_exc()
        return result

    def readline(self, size=None):
        if not self.__obj:
            return ''
        cdef char* data = <char*>EVBUFFER_PULLUP(self.__obj, -1)
        if not data:
            return ''

        cdef long length = evbuffer_get_length(self.__obj)
        cdef char *nl = <char*> memchr(<void*>data, 10, length)  # search for "\n"

        if nl:
            length = nl - data + 1

        cdef object result = PyString_FromStringAndSize(data, length)
        cdef int res = EVBUFFER_DRAIN(self.__obj, length)
        if res:
            try:
                sys.stderr.write('evbuffer_drain(0x%x, %s) returned %s\n' % (self._obj, length, res))
            except:
                traceback.print_exc()
        return result

    def readlines(self, hint=-1):
        return list(self)

    def write(self, bytes data):
        cdef int result = evbuffer_add(self.__obj, data, len(data))
        if result < 0:
            raise IOError("evbuffer_add() returned %s" % result)
        return result
