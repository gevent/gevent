`#' DO NOT EDIT -- this file is auto generated from __file__ on syscmd(date)
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
    cdef void IFDEF_WINDOWS "#if defined(_WIN32) //" ()
    cdef void IFDEF_EV_STANDALONE "#if defined(EV_STANDALONE) //" ()
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


cdef public class loop [object PyGeventLoopObject, type PyGeventLoop_Type]:
    cdef libev.ev_loop* _ptr
    cdef public object error_handler
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

    cpdef _stop_signal_checker(self):
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

    property activecnt:

        def __get__(self):
            res = None
            IFDEF_EV_STANDALONE()
            res = self._ptr.activecnt
            ENDIF()
            return res

    def io(self, int fd, int events):
        return io(self, fd, events)

    def timer(self, double after, double repeat=0.0):
        return timer(self, after, repeat)

    def signal(self, int signum):
        return signal(self, signum)

    def idle(self):
        return idle(self)

    def prepare(self):
        return prepare(self)

    def fork(self):
        return fork(self)

    def async(self):
        return async(self)

    def child(self, int pid, bint trace=0):
        return child(self, pid, trace)

    def callback(self):
        return callback(self)

    def run_callback(self, func, *args):
        cdef callback result = callback(self)
        result.start(func, *args)
        return result


define(INCREF, ``if self._incref == 0:
            self._incref = 1
            Py_INCREF(<PyObjectPtr>self)'')


define(WATCHER_BASE, `cdef public loop loop
    cdef object _callback
    cdef public tuple args
    cdef readonly int _incref   # 1 - increfed, 0 - not increfed
    cdef libev.ev_$1 _watcher

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
        libev.ev_$1_stop(self.loop._ptr, &self._watcher)
        self._callback = None
        self.args = None
        if self._incref == 1:
            Py_DECREF(<PyObjectPtr>self)
            self._incref = 0

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


define(INIT, `def __init__(self, loop loop$2):
        libev.ev_$1_init(&self._watcher, <void *>gevent_callback_$1$3)
        self.loop = loop
        self._incref = 0')


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

    def __cinit__(self):
        self._watcher.fd = -1;

    def __init__(self, loop loop, long fd, int events):
        cdef int vfd = libev.vfd_open(fd)
        libev.vfd_free(self._watcher.fd)
        libev.ev_io_init(&self._watcher, <void *>gevent_callback_io, vfd, events)
        self.loop = loop
        self._incref = 0

    def __dealloc__(self):
        libev.vfd_free(self._watcher.fd)

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


cdef public class timer(watcher) [object PyGeventTimerObject, type PyGeventTimer_Type]:

    WATCHER(timer)

    INIT(timer, ``, double after=0.0, double repeat=0.0'', ``, after, repeat'')

    property at:

        def __get__(self):
            return self._watcher.at


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


cdef public class child(watcher) [object PyGeventChildObject, type PyGeventChild_Type]:

    WATCHER(child)

    INIT(child, ``, int pid, bint trace=0'', ``, pid, trace'')



cdef public class callback(watcher) [object PyGeventCallbackObject, type PyGeventCallback_Type]:
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
