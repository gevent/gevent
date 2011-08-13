m4_dnl This is what core.pyx generated from. Run "make" to produce gevent.core.c extension.
# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
cimport cython
cimport libev
from python cimport *
import sys


__all__ = ['get_version',
           'get_header_version',
           'supported_backends',
           'recommended_backends',
           'embeddable_backends',
           'time',
           'loop']


cdef extern from "callbacks.h":
    void gevent_callback_io(libev.ev_loop, void*, int)
    void gevent_callback_timer(libev.ev_loop, void*, int)
    void gevent_callback_signal(libev.ev_loop, void*, int)
    void gevent_callback_idle(libev.ev_loop, void*, int)
    void gevent_callback_prepare(libev.ev_loop, void*, int)
    void gevent_callback_fork(libev.ev_loop, void*, int)
    void gevent_callback_async(libev.ev_loop, void*, int)
    void gevent_callback_child(libev.ev_loop, void*, int)
    void gevent_signal_check(libev.ev_loop, void*, int)
    void gevent_periodic_signal_check(libev.ev_loop, void*, int)

cdef extern from *:
    int FD_SETSIZE
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


@cython.internal
cdef class EVENTSType:
    """A special object to pass to watcher.start which gets replaced by *events* that fired.

    For example, if watcher is started as:
        >>> io = loop.io(1, READ|WRITE)
        >>> io.start(callback, EVENTS, 'hello')

    Then the callback will be called with 2 arguments:
        1) integer representing the event fired (READ, WRITE, READ|WRITE)
        2) 'hello'
    """
    def __repr__(self):
        return 'gevent.core.EVENTS'


cdef public object GEVENT_CORE_EVENTS = EVENTSType()
EVENTS = GEVENT_CORE_EVENTS


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


if sys.version_info[0] >= 3:
    basestring = (bytes, str)
else:
    basestring = __builtins__.basestring


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


cdef str _str_hex(object flag):
    if isinstance(flag, (int, long)):
        return hex(flag)
    return str(flag)


cpdef _check_flags(unsigned int flags):
    cdef list as_list
    flags &= libev.EVBACKEND_MASK
    if not flags:
        return
    if not (flags & libev.EVBACKEND_ALL):
        raise ValueError('Invalid value for backend: 0x%x' % flags)
    if not (flags & libev.ev_supported_backends()):
        as_list = [_str_hex(x) for x in _flags_to_list(flags)]
        raise ValueError('Unsupported backend: %s' % '|'.join(as_list))


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


m4_define(LOOP_PROPERTY, ``property $1:

        def __get__(self):
            return self._ptr.$1'')


cdef public class loop [object PyGeventLoopObject, type PyGeventLoop_Type]:
    cdef libev.ev_loop* _ptr
    cdef public object error_handler
    cdef libev.ev_prepare _signal_checker
#ifdef _WIN32
    cdef libev.ev_timer _periodic_signal_checker
#endif

    def __init__(self, object flags=None, object default=True, size_t ptr=0):
        cdef unsigned int c_flags
        libev.ev_prepare_init(&self._signal_checker, <void*>gevent_signal_check)
#ifdef _WIN32
        libev.ev_timer_init(&self._periodic_signal_checker, <void*>gevent_periodic_signal_check, 0.3, 0.3)
#endif
        if ptr:
            self._ptr = <libev.ev_loop*>ptr
        else:
            c_flags = _flags_to_int(flags)
            _check_flags(c_flags)
            if default:
                self._ptr = libev.ev_default_loop(c_flags)
                if not self._ptr:
                    raise SystemError("ev_default_loop(%s) failed" % (c_flags, ))
                libev.ev_prepare_start(self._ptr, &self._signal_checker)
                libev.ev_unref(self._ptr)
#ifdef _WIN32
                libev.ev_timer_start(self._ptr, &self._periodic_signal_checker)
                libev.ev_unref(self._ptr)
#endif
            else:
                self._ptr = libev.ev_loop_new(c_flags)
                if not self._ptr:
                    raise SystemError("ev_loop_new(%s) failed" % (c_flags, ))

    cpdef _stop_signal_checker(self):
        if libev.ev_is_active(&self._signal_checker):
            libev.ev_ref(self._ptr)
            libev.ev_prepare_stop(self._ptr, &self._signal_checker)
#ifdef _WIN32
        if libev.ev_is_active(&self._periodic_signal_checker):
            libev.ev_ref(self._ptr)
            libev.ev_timer_stop(self._ptr, &self._periodic_signal_checker)
#endif

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

    property WatcherType:

        def __get__(self):
            return watcher

    property MAXPRI:

       def __get__(self):
           return libev.EV_MAXPRI

    property MINPRI:

        def __get__(self):
            return libev.EV_MINPRI

    cpdef handle_error(self, context, type, value, tb):
        cdef object handle_error
        cdef object error_handler = self.error_handler
        if error_handler is not None:
            # we do want to do getattr every time so that setting Hub.handle_error property just works
            handle_error = getattr(error_handler, 'handle_error', error_handler)
            handle_error(context, type, value, tb)
        else:
            self._default_handle_error(context, type, value, tb)

    cpdef _default_handle_error(self, context, type, value, tb):
        # note: Hub sets its own error handler so this is not used by gevent
        # this is here to make core.loop usable without the rest of gevent
        import traceback
        traceback.print_exception(type, value, tb)
        libev.ev_break(self._ptr, libev.EVBREAK_ONE)

    def run(self, nowait=False, once=False):
        cdef unsigned int flags = 0
        if nowait:
            flags |= libev.EVRUN_NOWAIT
        if once:
            flags |= libev.EVRUN_ONCE
        with nogil:
            libev.ev_run(self._ptr, flags)

    def reinit(self):
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

    def update(self):
        libev.ev_now_update(self._ptr)

    def __repr__(self):
        result = '<%s at 0x%x' % (self.__class__.__name__, id(self))
        result += self._format()
        return result + '>'

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

    def io(self, int fd, int events, ref=True):
        return io(self, fd, events, ref)

    def timer(self, double after, double repeat=0.0, ref=True):
        return timer(self, after, repeat, ref)

    def signal(self, int signum, ref=True):
        return signal(self, signum, ref)

    def idle(self, ref=True):
        return idle(self, ref)

    def prepare(self, ref=True):
        return prepare(self, ref)

    def fork(self, ref=True):
        return fork(self, ref)

    def async(self, ref=True):
        return async(self, ref)

    #def child(self, int pid, bint trace=0):
    #    return child(self, pid, trace)

    def callback(self):
        return callback(self)

    def run_callback(self, func, *args):
        cdef callback result = callback(self)
        result.start(func, *args)
        return result

#ifdef EV_STANDALONE
    def _format(self):
        args = (self.default, self.backend, self.activecnt, self.backend_fd, self.fdchangecnt, self.timercnt)
        return  ' default=%r backend=%r activecnt=%r backend_fd=%r fdchangecnt=%r timercnt=%r' % args
#else
    def _format(self):
        args = (self.default, self.backend)
        return  ' default=%r backend=%r' % args
#endif

#ifdef EV_STANDALONE
    LOOP_PROPERTY(activecnt)
    LOOP_PROPERTY(backend_fd)
    LOOP_PROPERTY(fdchangecnt)
    LOOP_PROPERTY(timercnt)
#endif


m4_define(PYTHON_INCREF, ``if not self._flags & 1:
            Py_INCREF(<PyObjectPtr>self)
            self._flags |= 1'')m4_dnl

m4_define(LIBEV_UNREF, ``if self._flags & 6 == 4:
            libev.ev_unref(self.loop._ptr)
            self._flags |= 2'')m4_dnl

m4_define(WATCHER_BASE, `cdef public loop loop
    cdef object _callback
    cdef public tuple args

    # bit #1 set if object owns Python reference to itself (Py_INCREF was called and we must call Py_DECREF later)
    # bit #2 set if ev_unref() was called and we must call ev_ref() later
    # bit #3 set if user wants to call ev_unref() before start()
    cdef readonly int _flags

    cdef libev.ev_$1 _watcher

    property ref:

        def __get__(self):
            return False if self._flags & 4 else True

        def __set__(self, object value):
            if value:
                if not self._flags & 4:
                    return  # ref is already True
                if self._flags & 2:  # ev_unref was called, undo
                    libev.ev_ref(self.loop._ptr)
                self._flags &= ~6  # do not want unref, no outstanding unref
            else:
                if self._flags & 4:
                    return  # ref is already False
                self._flags |= 4
                if not self._flags & 2 and libev.ev_is_active(&self._watcher):
                    libev.ev_unref(self.loop._ptr)
                    self._flags |= 2

    property callback:

        def __get__(self):
            return self._callback

        def __set__(self, object callback):
            if not PyCallable_Check(<PyObjectPtr>callback):
                raise TypeError("Expected callable, not %r" % callback)
            self._callback = callback

        def __del__(self):
            self._callback = None

    def stop(self):
        if self._flags & 2:
            libev.ev_ref(self.loop._ptr)
            self._flags &= ~2
        libev.ev_$1_stop(self.loop._ptr, &self._watcher)
        self._callback = None
        self.args = None
        if self._flags & 1:
            Py_DECREF(<PyObjectPtr>self)
            self._flags &= ~1

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
        LIBEV_UNREF
        libev.ev_feed_event(self.loop._ptr, &self._watcher, revents)
        PYTHON_INCREF')m4_dnl

m4_define(ACTIVE, `property active:

        def __get__(self):
            return True if libev.ev_is_active(&self._watcher) else False')m4_dnl

m4_define(START, `def start(self, object callback, *args):
        self.callback = callback
        self.args = args
        LIBEV_UNREF
        libev.ev_$1_start(self.loop._ptr, &self._watcher)
        PYTHON_INCREF')m4_dnl

m4_define(WATCHER, `WATCHER_BASE($1)

    START($1)

    ACTIVE($1)')m4_dnl

m4_define(INIT, `def __init__(self, loop loop$2, ref=True):
        libev.ev_$1_init(&self._watcher, <void *>gevent_callback_$1$3)
        self.loop = loop
        if ref:
            self._flags = 0
        else:
            self._flags = 4')m4_dnl

cdef public class watcher [object PyGeventWatcherObject, type PyGeventWatcher_Type]:
    """Abstract base class for all the watchers"""

    def __repr__(self):
        if Py_ReprEnter(<PyObjectPtr>self) != 0:
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
            return result + ">"
        finally:
            Py_ReprLeave(<PyObjectPtr>self)

    def _format(self):
        return ''


cdef public class io(watcher) [object PyGeventIOObject, type PyGeventIO_Type]:

    WATCHER(io)

#ifdef _WIN32

    def __init__(self, loop loop, long fd, int events, ref=True):
        cdef int vfd = libev.vfd_open(fd)
        libev.vfd_free(self._watcher.fd)
        libev.ev_io_init(&self._watcher, <void *>gevent_callback_io, vfd, events)
        self.loop = loop
        if ref:
            self._flags = 0
        else:
            self._flags = 4

#else

    def __init__(self, loop loop, int fd, int events, ref=True):
        libev.ev_io_init(&self._watcher, <void *>gevent_callback_io, fd, events)
        self.loop = loop
        if ref:
            self._flags = 0
        else:
            self._flags = 4

#endif

    property fd:

        def __get__(self):
            return libev.vfd_get(self._watcher.fd)

        def __set__(self, long fd):
            if libev.ev_is_active(&self._watcher):
                raise AttributeError("'io' watcher attribute 'fd' is read-only while watcher is active")
            cdef int vfd = libev.vfd_open(fd)
            libev.vfd_free(self._watcher.fd)
            libev.ev_io_init(&self._watcher, <void *>gevent_callback_io, vfd, self._watcher.events)

    property events:

        def __get__(self):
            return self._watcher.events

        def __set__(self, int events):
            if libev.ev_is_active(&self._watcher):
                raise AttributeError("'io' watcher attribute 'events' is read-only while watcher is active")
            libev.ev_io_init(&self._watcher, <void *>gevent_callback_io, self._watcher.fd, events)

    property events_str:

        def __get__(self):
            return _events_to_str(self._watcher.events)

    def _format(self):
        return ' fd=%s events=%s' % (self.fd, self.events_str)

#ifdef _WIN32

    def __cinit__(self):
        self._watcher.fd = -1;

    def __dealloc__(self):
        libev.vfd_free(self._watcher.fd)

#endif


cdef public class timer(watcher) [object PyGeventTimerObject, type PyGeventTimer_Type]:

    WATCHER(timer)

    INIT(timer, ``, double after=0.0, double repeat=0.0'', ``, after, repeat'')

    property at:

        def __get__(self):
            return self._watcher.at

    def again(self, object callback, *args):
        self.callback = callback
        self.args = args
        LIBEV_UNREF
        libev.ev_timer_again(self.loop._ptr, &self._watcher)
        PYTHON_INCREF


cdef public class signal(watcher) [object PyGeventSignalObject, type PyGeventSignal_Type]:

    WATCHER(signal)

    INIT(signal, ``, int signalnum'', ``, signalnum'')


cdef public class idle(watcher) [object PyGeventIdleObject, type PyGeventIdle_Type]:

    WATCHER(idle)

    INIT(idle)


cdef public class prepare(watcher) [object PyGeventPrepareObject, type PyGeventPrepare_Type]:

    WATCHER(prepare)

    INIT(prepare)


cdef public class fork(watcher) [object PyGeventForkObject, type PyGeventFork_Type]:

    WATCHER(fork)

    INIT(fork)


cdef public class async(watcher) [object PyGeventAsyncObject, type PyGeventAsync_Type]:

    WATCHER(async)

    INIT(async)


#cdef public class child(watcher) [object PyGeventChildObject, type PyGeventChild_Type]:
#
#    WATCHER(child)
#
#    INIT(child, ``, int pid, bint trace=0'', ``, pid, trace'')


cdef public class callback(watcher) [object PyGeventCallbackObject, type PyGeventCallback_Type]:
    """Pseudo-watcher used to execute a callback in the loop as soon as possible."""

    # does not matter which type we actually use, since we are going to feed() events, not start watchers
    WATCHER_BASE(prepare)

    INIT(prepare)

    def start(self, object callback, *args):
        self.callback = callback
        self.args = args
        libev.ev_feed_event(self.loop._ptr, &self._watcher, libev.EV_CUSTOM)
        PYTHON_INCREF

    property active:

        def __get__(self):
            return self.callback is not None


def set_exc_info(object type, object value):
    cdef PyThreadState* tstate = PyThreadState_GET()
    Py_XDECREF(tstate.exc_type)
    Py_XDECREF(tstate.exc_value)
    Py_XDECREF(tstate.exc_traceback)
    if type is None:
        tstate.exc_type = NULL
    else:
        Py_INCREF(<PyObjectPtr>type)
        tstate.exc_type = <PyObjectPtr>type
    if value is None:
        tstate.exc_value = NULL
    else:
        Py_INCREF(<PyObjectPtr>value)
        tstate.exc_value = <PyObjectPtr>value
    tstate.exc_traceback = NULL
