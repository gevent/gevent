cimport libev


__all__ = ['get_version',
           'get_header_version',
           'supported_backends',
           'recommended_backends',
           'embeddable_backends',
           'time',
           'loop']


cdef extern from "Python.h":
    void   Py_INCREF(void* o)
    void   Py_DECREF(void* o)
    void   Py_XDECREF(void* o)
    int    Py_ReprEnter(void* o)
    void   Py_ReprLeave(void* o)

cdef extern from "frameobject.h":
    ctypedef struct PyThreadState:
        void* exc_type
        void* exc_value
        void* exc_traceback
    PyThreadState* PyThreadState_GET()

cdef extern from "callbacks.h":
    void gevent_io_callback(libev.ev_loop, libev.ev_io, int)
    void gevent_simple_callback(libev.ev_loop, void*, int)
    void gevent_signal_check(libev.ev_loop, void*, int)
    void gevent_periodic_signal_check(libev.ev_loop, void*, int)


cdef extern from *:
    int FD_SETSIZE
    int _open_osfhandle(int, int)
    cdef void IFDEF_WINDOWS "#if defined(GEVENT_WINDOWS) //" ()
    cdef void ENDIF "#endif //" ()
    int ioctlsocket(int, int, unsigned long*)
    int FIONREAD


UNDEF = libev.EV_UNDEF
NONE = libev.EV_NONE
READ = libev.EV_READ
WRITE = libev.EV_WRITE
TIMER = libev.EV_TIMER
PERIODIC = libev.EV_PERIODIC
SIGNAL = libev.EV_SIGNAL
CHILD = libev.EV_CHILD
STAT = libev.EV_STAT
IDLE = libev.EV_IDLE
PREPARE = libev.EV_PREPARE
CHECK = libev.EV_CHECK
EMBED = libev.EV_EMBED
FORK = libev.EV_FORK
CLEANUP = libev.EV_CLEANUP
ASYNC = libev.EV_ASYNC
CUSTOM = libev.EV_CUSTOM
ERROR = libev.EV_ERROR

READWRITE = libev.EV_READ | libev.EV_WRITE

MINPRI = libev.EV_MINPRI
MAXPRI = libev.EV_MAXPRI

BACKEND_PORT = libev.EVBACKEND_PORT
BACKEND_KQUEUE = libev.EVBACKEND_KQUEUE
BACKEND_EPOLL = libev.EVBACKEND_EPOLL
BACKEND_POLL = libev.EVBACKEND_POLL
BACKEND_SELECT = libev.EVBACKEND_SELECT
NOENV = libev.EVFLAG_NOENV
FORKCHECK = libev.EVFLAG_FORKCHECK
NOINOTIFY = libev.EVFLAG_NOINOTIFY
SIGNALFD = libev.EVFLAG_SIGNALFD
NOSIGMASK = libev.EVFLAG_NOSIGMASK


def get_version():
    return 'libev-%d.%02d' % (libev.ev_version_major(), libev.ev_version_minor())


def get_header_version():
    return 'libev-%d.%02d' % (libev.EV_VERSION_MAJOR, libev.EV_VERSION_MINOR)


# This list backends in the order they are actually tried by libev
_flags = [(libev.EVBACKEND_PORT, 'port'),
          (libev.EVBACKEND_KQUEUE, 'kqueue'),
          (libev.EVBACKEND_EPOLL, 'epoll'),
          (libev.EVBACKEND_POLL, 'poll'),
          (libev.EVBACKEND_SELECT, 'select'),
          (libev.EVFLAG_NOENV, 'noenv'),
          (libev.EVFLAG_FORKCHECK, 'forkcheck'),
          (libev.EVFLAG_SIGNALFD, 'signalfd'),
          (libev.EVFLAG_NOSIGMASK, 'nosigmask')]


_flags_str2int = dict((string, flag) for (flag, string) in _flags)


_events = [(libev.EV_READ,     'READ'),
           (libev.EV_WRITE,    'WRITE'),
           (libev.EV__IOFDSET, '_IOFDSET'),
           (libev.EV_PERIODIC, 'PERIODIC'),
           (libev.EV_SIGNAL,   'SIGNAL'),
           (libev.EV_CHILD,    'CHILD'),
           (libev.EV_STAT,     'STAT'),
           (libev.EV_IDLE,     'IDLE'),
           (libev.EV_PREPARE,  'PREPARE'),
           (libev.EV_CHECK,    'CHECK'),
           (libev.EV_EMBED,    'EMBED'),
           (libev.EV_FORK,     'FORK'),
           (libev.EV_CLEANUP,  'CLEANUP'),
           (libev.EV_ASYNC,    'ASYNC'),
           (libev.EV_CUSTOM,   'CUSTOM'),
           (libev.EV_ERROR,    'ERROR')]


cpdef _flags_to_list(unsigned int flags):
    cdef list result = []
    for code, value in _flags:
        if flags & code:
            result.append(value)
        flags &= ~code
        if not flags:
            break
    if flags:
        result.append(flags)
    return result


cpdef unsigned int _flags_to_int(object flags) except? -1:
    # Note, that order does not matter, libev has its own predefined order
    if flags is None:
        return 0
    if isinstance(flags, (int, long)):
        return flags
    cdef unsigned int result = 0
    try:
        if isinstance(flags, basestring):
            return _flags_str2int[flags.lower()]
        for value in flags:
            result |= _flags_str2int[value.lower()]
    except KeyError, ex:
        raise ValueError('Invalid backend or flag: %s\nPossible values: %s' % (ex, ', '.join(sorted(_flags_str2int.keys()))))
    return result


cpdef _events_to_str(int events):
    cdef list result = []
    cdef int c_flag
    for (flag, string) in _events:
        c_flag = flag
        if events & c_flag:
            result.append(string)
            events = events & (~c_flag)
        if not events:
            break
    if events:
        result.append(hex(events))
    return '|'.join(result)


def supported_backends():
    return _flags_to_list(libev.ev_supported_backends())


def recommended_backends():
    return _flags_to_list(libev.ev_recommended_backends())


def embeddable_backends():
    return _flags_to_list(libev.ev_embeddable_backends())


def time(self):
    return libev.ev_time()


cdef class loop:
    cdef libev.ev_loop* _ptr
    cdef public object handle_error
    cdef libev.ev_prepare _signal_checker
    cdef libev.ev_timer _periodic_signal_checker

    def __init__(self, object flags=None, object default=True, size_t ptr=0):
        cdef unsigned int c_flags
        libev.ev_prepare_init(&self._signal_checker, <void*>gevent_signal_check)
        IFDEF_WINDOWS()
        libev.ev_timer_init(&self._periodic_signal_checker, <void*>gevent_periodic_signal_check, 0.3, 0.3)
        ENDIF()
        if ptr:
            self._ptr = <libev.ev_loop*>ptr
        else:
            c_flags = _flags_to_int(flags)
            if default:
                self._ptr = libev.ev_default_loop(c_flags)
                if not self._ptr:
                    raise SystemError("ev_default_loop(%s) failed" % (c_flags, ))
                libev.ev_prepare_start(self._ptr, &self._signal_checker)
                libev.ev_unref(self._ptr)
                IFDEF_WINDOWS()
                libev.ev_timer_start(self._ptr, &self._periodic_signal_checker)
                libev.ev_unref(self._ptr)
                ENDIF()
            else:
                self._ptr = libev.ev_loop_new(c_flags)
                if not self._ptr:
                    raise SystemError("ev_loop_new(%s) failed" % (c_flags, ))

    def _stop_signal_checker(self):
        if libev.ev_is_active(&self._signal_checker):
            libev.ev_ref(self._ptr)
            libev.ev_prepare_stop(self._ptr, &self._signal_checker)
        IFDEF_WINDOWS()
        if libev.ev_is_active(&self._periodic_signal_checker):
            libev.ev_ref(self._ptr)
            libev.ev_timer_stop(self._ptr, &self._periodic_signal_checker)
        ENDIF()

    def destroy(self):
        if self._ptr:
            self._stop_signal_checker()
            libev.ev_loop_destroy(self._ptr)
            self._ptr = NULL

    def __dealloc__(self):
        if self._ptr:
            self._stop_signal_checker()
            if not libev.ev_is_default_loop(self._ptr):
                libev.ev_loop_destroy(self._ptr)
            self._ptr = NULL

    property ptr:

        def __get__(self):
            return <size_t>self._ptr

    def _default_handle_error(self, where, type, value, tb):
        # note: Hub sets its own error handler so this is not used by gevent
        # this is here to make core.loop usable without the rest of gevent
        import traceback
        traceback.print_exception(type, value, tb)
        libev.ev_break(self._ptr, libev.EVBREAK_ONE)

    def run(self, nowait=False, once=False, object handle_error=None):
        cdef unsigned int flags = 0
        if nowait:
            flags |= libev.EVRUN_NOWAIT
        if once:
            flags |= libev.EVRUN_ONCE
        if handle_error is None:
            if self.handle_error is None:
                self.handle_error = self._default_handle_error
                handle_error = False
        else:
            self.handle_error = handle_error
        with nogil:
            libev.ev_run(self._ptr, flags)
        if handle_error is False:
            self.handle_error = None

    def fork(self):
        libev.ev_loop_fork(self._ptr)

    def ref(self):
        libev.ev_ref(self._ptr)

    def unref(self):
        libev.ev_unref(self._ptr)

    def break_(self, int how=libev.EVBREAK_ONE):
        libev.ev_break(self._ptr, how)

    def verify(self):
        libev.ev_verify(self._ptr)

    def now(self):
        return libev.ev_now(self._ptr)

    def update_now(self):
        libev.ev_now_update(self._ptr)

    property default:

        def __get__(self):
            return True if libev.ev_is_default_loop(self._ptr) else False

    property iteration:

        def __get__(self):
            return libev.ev_iteration(self._ptr)

    property depth:

        def __get__(self):
            return libev.ev_depth(self._ptr)

    property backend_int:

        def __get__(self):
            return libev.ev_backend(self._ptr)

    property backend:

        def __get__(self):
            cdef unsigned int backend = libev.ev_backend(self._ptr)
            for key, value in _flags:
                if key == backend:
                    return value
            return backend

    property activecnt:  # XXX only available if we embed libev

        def __get__(self):
            return self._ptr.activecnt

    def io(self, int fd, int events):
        return io(self, fd, events)

    def io_ref(self, int fd, int events):
        return io(self, fd, events, True)

    def timer(self, double after, double repeat=0.0):
        return timer(self, after, repeat)

    def timer_ref(self, double after, double repeat=0.0):
        return timer(self, after, repeat, True)

    def signal(self, int signum):
        return signal(self, signum)

    def signal_ref(self, int signum):
        return signal(self, signum, True)

    def idle(self):
        return idle(self)

    def idle_ref(self):
        return idle(self, True)

    def prepare(self):
        return prepare(self)

    def prepare_ref(self):
        return prepare(self, True)

    def callback(self):
        return callback(self)

    def callback_ref(self):
        return callback(self, True)

    def run_callback(self, func, *args):
        cdef object result = callback(self, ref=True)
        result.start(func, *args)
        return result


define(INCREF, ``if self._incref == 1:
            self._incref = 2
            Py_INCREF(<void*>self)'')


define(WATCHER_BASE, `cdef public loop loop
    cdef public object callback
    cdef public object args
    cdef public int _incref   # 0 - disabled, 1 - enabled, 2 - enabled & increfed
    cdef libev.ev_$1 _watcher

    def stop(self):
        libev.ev_$1_stop(self.loop._ptr, &self._watcher)
        self.callback = None
        self.args = None
        if self._incref == 2:
            Py_DECREF(<void*>self)
            self._incref = 1

    def __dealloc__(self):
        libev.ev_$1_stop(self.loop._ptr, &self._watcher)

    property pending:

        def __get__(self):
            return True if libev.ev_is_pending(&self._watcher) else False

    property priority:

        def __get__(self):
            return libev.ev_priority(&self._watcher)

        def __set__(self, int priority):
            if libev.ev_is_active(&self._watcher):
                raise AttributeError("Cannot set priority of an active watcher")
            libev.ev_set_priority(&self._watcher, priority)

    def feed(self, int revents, object callback, *args):
        self.callback = callback
        self.args = args
        libev.ev_feed_event(self.loop._ptr, &self._watcher, revents)
        INCREF')


define(ACTIVE, `property active:

        def __get__(self):
            return True if libev.ev_is_active(&self._watcher) else False')


define(START, `def start(self, object callback, *args):
        self.callback = callback
        self.args = args
        libev.ev_$1_start(self.loop._ptr, &self._watcher)
        INCREF')


define(WATCHER, `WATCHER_BASE($1)

    START($1)

    ACTIVE($1)')


define(INIT, `def __init__(self, loop loop$2, object ref=False):
        libev.ev_$1_init(&self._watcher, <void *>gevent_simple_callback$3)
        self.loop = loop
        if ref:
            self._incref = 1
        else:
            self._incref = 0')


cdef class watcher:
    """Abstract base class for all the watchers"""

    def __repr__(self):
        if Py_ReprEnter(<void*>self) != 0:
            return "<...>"
        try:
            format = self._format()
            result = "<%s at 0x%x%s" % (self.__class__.__name__, id(self), format)
            if self.active:
                result += " active"
            if self.pending:
                result += " pending"
            if self.callback is not None:
                result += " callback=%r" % (self.callback, )
            if self.args is not None:
                result += " args=%r" % (self.args, )
            if self._incref == 2:
                result += " REF"
            elif self._incref == 1:
                result += " ref"
            elif self._incref:
                result += " _incref=%s" % self._incref
            return result + ">"
        finally:
            Py_ReprLeave(<void*>self)

    def _format(self):
        return ''


cdef int _get_fd(int handle) except -1:
    cdef int fd = handle
    IFDEF_WINDOWS()
    fd = _open_osfhandle(fd, 0)
    if fd < 0:
        raise IOError("handle=%s does not have a valid file descriptor" % handle)
    if fd >= FD_SETSIZE:
        raise IOError("fd %s (handle=%s) is bigger than FD_SETSIZE (%s)" % (fd, handle, FD_SETSIZE))
    cdef unsigned long arg
    if ioctlsocket(handle, FIONREAD, &arg) != 0:
        raise IOError("fd=%s (handle=%s) is not a socket descriptor (file descriptors are not supported)" % (fd, handle))
    ENDIF()
    return fd


cdef class io(watcher):

    WATCHER(io)

    def __init__(self, loop loop, int fd, int events, object ref=False):
        IFDEF_WINDOWS()
        fd = _get_fd(fd)
        ENDIF()
        libev.ev_io_init(&self._watcher, <void *>gevent_io_callback, fd, events)
        self.loop = loop
        if ref:
            self._incref = 1
        else:
            self._incref = 0

    property fd:

        def __get__(self):
            return self._watcher.fd

        def __set__(self, int fd):
            if libev.ev_is_active(&self._watcher):
                raise AttributeError("'io' watcher attribute 'fd' is read-only while watcher is active")
            libev.ev_io_init(&self._watcher, <void *>gevent_io_callback, fd, self._watcher.events)

    property events:

        def __get__(self):
            return self._watcher.events

        def __set__(self, int events):
            if libev.ev_is_active(&self._watcher):
                raise AttributeError("'io' watcher attribute 'events' is read-only while watcher is active")
            libev.ev_io_init(&self._watcher, <void *>gevent_io_callback, self._watcher.fd, events)

    property events_str:

        def __get__(self):
            return _events_to_str(self._watcher.events)

    def _format(self):
        return ' fd=%s events=%s' % (self._watcher.fd, self.events_str)


cdef class timer(watcher):

    WATCHER(timer)

    INIT(timer, ``, double after=0.0, double repeat=0.0'', ``, after, repeat'')

    property at:

        def __get__(self):
            return self._watcher.at


cdef class signal(watcher):

    WATCHER(signal)

    INIT(signal, ``, int signalnum'', ``, signalnum'')


cdef class idle(watcher):

    WATCHER(idle)

    INIT(idle)


cdef class prepare(watcher):

    WATCHER(prepare)

    INIT(prepare)


cdef class callback(watcher):
    """Pseudo-watcher used to execute a callback in the loop as soon as possible."""

    # does not matter which type we actually use, since we are going to feed() events, not start watchers
    WATCHER_BASE(prepare)

    INIT(prepare)

    def start(self, object callback, *args):
        self.callback = callback
        self.args = args
        libev.ev_feed_event(self.loop._ptr, &self._watcher, libev.EV_CUSTOM)
        INCREF

    property active:

        def __get__(self):
            return self.callback is not None


def set_exc_info(object type, object value):
    cdef PyThreadState* tstate = PyThreadState_GET()
    Py_XDECREF(<void*>tstate.exc_type)
    Py_XDECREF(<void*>tstate.exc_value)
    Py_XDECREF(<void*>tstate.exc_traceback)
    if value is None:
        tstate.exc_type = NULL
        tstate.exc_value = NULL
    else:
        Py_INCREF(<void*>type)
        Py_INCREF(<void*>value)
        tstate.exc_type = <void*>type
        tstate.exc_value = <void *>value
    tstate.exc_traceback = NULL
