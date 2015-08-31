from __future__ import absolute_import
import sys
import os
import traceback
import signal as signalmodule
import struct


__all__ = ['get_version',
           'get_header_version',
           'supported_backends',
           'recommended_backends',
           'embeddable_backends',
           'time',
           'loop']


def system_bits():
    return struct.calcsize('P') * 8


def st_nlink_type():
    if sys.platform == "darwin":
        return "short"
    elif system_bits() == 32:
        return "unsigned long"
    return "long long"

import cffi
if cffi.__version_info__ >= (1, 2, 0):
    # See https://bitbucket.org/cffi/cffi/issue/152/handling-errors-from-signal-handlers-in.
    # With this version, bundled with PyPy 2.6.1 and above, we can more reliably
    # handle signals and other exceptions. With this support, we could simplify
    # _python_callback and _python_handle_error in addition to the simplifications for
    # signals and KeyboardInterrupt. However, because we need to support PyPy 2.5.0+,
    # we keep as much as practical shared.
    _cffi_supports_on_error = True
else:
    # In older versions, including the 2.5.0 currently on Travis CI, we
    # have to use a kludge
    _cffi_supports_on_error = False

from cffi import FFI
ffi = FFI()
_cdef = """
#define EV_MINPRI ...
#define EV_MAXPRI ...

#define EV_VERSION_MAJOR ...
#define EV_VERSION_MINOR ...

#define EV_UNDEF ...
#define EV_NONE ...
#define EV_READ ...
#define EV_WRITE ...
#define EV__IOFDSET ...
#define EV_TIMER ...
#define EV_PERIODIC ...
#define EV_SIGNAL ...
#define EV_CHILD ...
#define EV_STAT ...
#define EV_IDLE ...
#define EV_PREPARE ...
#define EV_CHECK ...
#define EV_EMBED ...
#define EV_FORK ...
#define EV_CLEANUP ...
#define EV_ASYNC ...
#define EV_CUSTOM ...
#define EV_ERROR ...

#define EVFLAG_AUTO ...
#define EVFLAG_NOENV ...
#define EVFLAG_FORKCHECK ...
#define EVFLAG_NOINOTIFY ...
#define EVFLAG_SIGNALFD ...
#define EVFLAG_NOSIGMASK ...

#define EVBACKEND_SELECT ...
#define EVBACKEND_POLL ...
#define EVBACKEND_EPOLL ...
#define EVBACKEND_KQUEUE ...
#define EVBACKEND_DEVPOLL ...
#define EVBACKEND_PORT ...
/* #define EVBACKEND_IOCP ... */

#define EVBACKEND_ALL ...
#define EVBACKEND_MASK ...

#define EVRUN_NOWAIT ...
#define EVRUN_ONCE ...

#define EVBREAK_CANCEL ...
#define EVBREAK_ONE ...
#define EVBREAK_ALL ...

struct ev_loop {
    int backend_fd;
    int activecnt;
    ...;
};
struct ev_io {
    int fd;
    int events;
    ...;
};
struct ev_timer {
    double at;
    ...;
};
struct ev_signal {...;};
struct ev_idle  {...;};
struct ev_prepare {...;};
struct ev_check {...;};
struct ev_fork  {...;};
struct ev_async  {...;};
struct ev_child {
    int pid;
    int rpid;
    int rstatus;
    ...;
};
struct stat {
    """ + st_nlink_type() + """ st_nlink;
    ...;
};

struct ev_stat {
    struct stat attr;
    const char* path;
    struct stat prev;
    double interval;
    ...;
};

typedef double ev_tstamp;

int ev_version_major();
int ev_version_minor();

unsigned int ev_supported_backends (void);
unsigned int ev_recommended_backends (void);
unsigned int ev_embeddable_backends (void);

ev_tstamp ev_time (void);
void ev_set_syserr_cb(void *);

int ev_priority(void*);
void ev_set_priority(void*, int);

int ev_is_pending(void*);
int ev_is_active(void*);
void ev_io_init(struct ev_io*, void* callback, int fd, int events);
void ev_io_start(struct ev_loop*, struct ev_io*);
void ev_io_stop(struct ev_loop*, struct ev_io*);
void ev_feed_event(struct ev_loop*, void*, int);

void ev_timer_init(struct ev_timer*, void (*callback)(struct ev_loop *_loop, struct ev_timer *w, int revents), double, double);
void ev_timer_start(struct ev_loop*, struct ev_timer*);
void ev_timer_stop(struct ev_loop*, struct ev_timer*);
void ev_timer_again(struct ev_loop*, struct ev_timer*);

void ev_signal_init(struct ev_signal*, void* callback, int);
void ev_signal_start(struct ev_loop*, struct ev_signal*);
void ev_signal_stop(struct ev_loop*, struct ev_signal*);

void ev_idle_init(struct ev_idle*, void* callback);
void ev_idle_start(struct ev_loop*, struct ev_idle*);
void ev_idle_stop(struct ev_loop*, struct ev_idle*);

void ev_prepare_init(struct ev_prepare*, void* callback);
void ev_prepare_start(struct ev_loop*, struct ev_prepare*);
void ev_prepare_stop(struct ev_loop*, struct ev_prepare*);

void ev_check_init(struct ev_check*, void* callback);
void ev_check_start(struct ev_loop*, struct ev_check*);
void ev_check_stop(struct ev_loop*, struct ev_check*);

void ev_fork_init(struct ev_fork*, void* callback);
void ev_fork_start(struct ev_loop*, struct ev_fork*);
void ev_fork_stop(struct ev_loop*, struct ev_fork*);

void ev_async_init(struct ev_async*, void* callback);
void ev_async_start(struct ev_loop*, struct ev_async*);
void ev_async_stop(struct ev_loop*, struct ev_async*);
void ev_async_send(struct ev_loop*, struct ev_async*);
int ev_async_pending(struct ev_async*);

void ev_child_init(struct ev_child*, void* callback, int, int);
void ev_child_start(struct ev_loop*, struct ev_child*);
void ev_child_stop(struct ev_loop*, struct ev_child*);

void ev_stat_init(struct ev_stat*, void* callback, char*, double);
void ev_stat_start(struct ev_loop*, struct ev_stat*);
void ev_stat_stop(struct ev_loop*, struct ev_stat*);

struct ev_loop *ev_default_loop (unsigned int flags);
struct ev_loop* ev_loop_new(unsigned int flags);
void ev_loop_destroy(struct ev_loop*);
void ev_loop_fork(struct ev_loop*);
int ev_is_default_loop (struct ev_loop *);
unsigned int ev_iteration(struct ev_loop*);
unsigned int ev_depth(struct ev_loop*);
unsigned int ev_backend(struct ev_loop*);
void ev_verify(struct ev_loop*);
void ev_run(struct ev_loop*, int flags);

ev_tstamp ev_now (struct ev_loop *);
void ev_now_update (struct ev_loop *); /* update event loop time */
void ev_ref(struct ev_loop*);
void ev_unref(struct ev_loop*);
void ev_break(struct ev_loop*, int);
unsigned int ev_pending_count(struct ev_loop*);

struct ev_loop* gevent_ev_default_loop(unsigned int flags);
void gevent_install_sigchld_handler();

void (*gevent_noop)(struct ev_loop *_loop, struct ev_timer *w, int revents);
void ev_sleep (ev_tstamp delay); /* sleep for a while */
"""


_watcher_types = ['ev_io',
                  'ev_timer',
                  'ev_signal',
                  'ev_prepare',
                  'ev_check',
                  'ev_fork',
                  'ev_async',
                  'ev_child',
                  'ev_stat',
                  'ev_idle', ]

_source = """   // passed to the real C compiler
#define LIBEV_EMBED 1
#include "libev.h"

static void
_gevent_noop(struct ev_loop *_loop, struct ev_timer *w, int revents) { }

void (*gevent_noop)(struct ev_loop *, struct ev_timer *, int) = &_gevent_noop;
"""

# Setup the watcher callbacks
_cbs = """
static int (*python_callback)(void* handle, int revents);
static void (*python_handle_error)(void* handle, int revents);
static void (*python_stop)(void* handle);
"""
_cdef += _cbs
_source += _cbs

for _watcher_type in _watcher_types:
    _cdef += """
   struct gevent_%s {
        struct %s watcher;
        void* handle;
        ...;
    };
    static void _gevent_%s_callback(struct ev_loop* loop, struct %s* watcher, int revents);
    """ % (_watcher_type, _watcher_type, _watcher_type, _watcher_type)

    _source += """
    struct gevent_%s {
        struct %s watcher;
        void* handle;
    };
    """ % (_watcher_type, _watcher_type)

    _source += """
    static void _gevent_%s_callback(struct ev_loop* loop, struct %s* watcher, int revents)
    {
        // invoke self.callback()
        void* handle = ((struct gevent_%s *)watcher)->handle;
        if( python_callback(handle, revents) < 0) {
            /* in case of exception, call self.loop.handle_error */
            python_handle_error(handle, revents);
        }
        // Code to stop the event
        if (!ev_is_active(watcher)) {
            python_stop(handle);
        }
    }
    """ % (_watcher_type, _watcher_type, _watcher_type)

thisdir = os.path.dirname(os.path.realpath(__file__))
include_dirs = [thisdir, os.path.join(thisdir, 'libev')]
ffi.cdef(_cdef)
libev = C = ffi.verify(_source, include_dirs=include_dirs)
del thisdir, include_dirs, _watcher_type, _watcher_types

libev.vfd_open = libev.vfd_get = lambda fd: fd
libev.vfd_free = lambda fd: None


@ffi.callback("int(void* handle, int revents)")
def _python_callback(handle, revents):
    watcher = ffi.from_handle(handle)
    if len(watcher.args) > 0 and watcher.args[0] == GEVENT_CORE_EVENTS:
        watcher.args = (revents, ) + watcher.args[1:]
    try:
        watcher.callback(*watcher.args)
    except:
        watcher._exc_info = sys.exc_info()
        return -1
    else:
        return 0
libev.python_callback = _python_callback

# After _python_callback is called, the handle may no longer be
# valid. The callback itself might have called watcher.stop(),
# which would remove the object from loop.keepaliveset, and if
# that was the last reference to it, the handle would be GC'd.
# Therefore the other functions need to correctly deal with an
# invalid handle


@ffi.callback("void(void* handle, int revents)")
def _python_handle_error(handle, revents):
    try:
        watcher = ffi.from_handle(handle)
    except RuntimeError:
        return

    exc_info = watcher._exc_info
    del watcher._exc_info
    try:
        watcher.loop.handle_error(watcher, *exc_info)
    finally:
        if revents & (libev.EV_READ | libev.EV_WRITE):
            try:
                watcher.stop()
            except:
                watcher.loop.handle_error(watcher, *sys.exc_info())
            return
libev.python_handle_error = _python_handle_error


@ffi.callback("void(void* handle)")
def _python_stop(handle):
    try:
        watcher = ffi.from_handle(handle)
    except RuntimeError:
        return
    watcher.stop()
libev.python_stop = _python_stop


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
FORKCHECK = libev.EVFLAG_FORKCHECK
NOINOTIFY = libev.EVFLAG_NOINOTIFY
SIGNALFD = libev.EVFLAG_SIGNALFD
NOSIGMASK = libev.EVFLAG_NOSIGMASK


class _EVENTSType(object):
    def __repr__(self):
        return 'gevent.core.EVENTS'

EVENTS = GEVENT_CORE_EVENTS = _EVENTSType()


def get_version():
    return 'libev-%d.%02d' % (C.ev_version_major(), C.ev_version_minor())


def get_header_version():
    return 'libev-%d.%02d' % (C.EV_VERSION_MAJOR, C.EV_VERSION_MINOR)

_flags = [(C.EVBACKEND_PORT, 'port'),
          (C.EVBACKEND_KQUEUE, 'kqueue'),
          (C.EVBACKEND_EPOLL, 'epoll'),
          (C.EVBACKEND_POLL, 'poll'),
          (C.EVBACKEND_SELECT, 'select'),
          (C.EVFLAG_NOENV, 'noenv'),
          (C.EVFLAG_FORKCHECK, 'forkcheck'),
          (C.EVFLAG_SIGNALFD, 'signalfd'),
          (C.EVFLAG_NOSIGMASK, 'nosigmask')]

_flags_str2int = dict((string, flag) for (flag, string) in _flags)

_events = [(libev.EV_READ, 'READ'),
           (libev.EV_WRITE, 'WRITE'),
           (libev.EV__IOFDSET, '_IOFDSET'),
           (libev.EV_PERIODIC, 'PERIODIC'),
           (libev.EV_SIGNAL, 'SIGNAL'),
           (libev.EV_CHILD, 'CHILD'),
           (libev.EV_STAT, 'STAT'),
           (libev.EV_IDLE, 'IDLE'),
           (libev.EV_PREPARE, 'PREPARE'),
           (libev.EV_CHECK, 'CHECK'),
           (libev.EV_EMBED, 'EMBED'),
           (libev.EV_FORK, 'FORK'),
           (libev.EV_CLEANUP, 'CLEANUP'),
           (libev.EV_ASYNC, 'ASYNC'),
           (libev.EV_CUSTOM, 'CUSTOM'),
           (libev.EV_ERROR, 'ERROR')]


def _flags_to_list(flags):
    result = []
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
    integer_types = int,
else:
    import __builtin__
    basestring = __builtin__.basestring
    integer_types = (int, __builtin__.long)


def _flags_to_int(flags):
    # Note, that order does not matter, libev has its own predefined order
    if not flags:
        return 0
    if isinstance(flags, integer_types):
        return flags
    result = 0
    try:
        if isinstance(flags, basestring):
            flags = flags.split(',')
        for value in flags:
            value = value.strip().lower()
            if value:
                result |= _flags_str2int[value]
    except KeyError as ex:
        raise ValueError('Invalid backend or flag: %s\nPossible values: %s' % (ex, ', '.join(sorted(_flags_str2int.keys()))))
    return result


def _str_hex(flag):
    if isinstance(flag, integer_types):
        return hex(flag)
    return str(flag)


def _check_flags(flags):
    as_list = []
    flags &= libev.EVBACKEND_MASK
    if not flags:
        return
    if not (flags & libev.EVBACKEND_ALL):
        raise ValueError('Invalid value for backend: 0x%x' % flags)
    if not (flags & libev.ev_supported_backends()):
        as_list = [_str_hex(x) for x in _flags_to_list(flags)]
        raise ValueError('Unsupported backend: %s' % '|'.join(as_list))


def _events_to_str(events):
    result = []
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


def time():
    return C.ev_time()

_default_loop_destroyed = False


def _loop_callback(*args, **kwargs):
    if _cffi_supports_on_error:
        return ffi.callback(*args, **kwargs)
    kwargs.pop('onerror')
    return ffi.callback(*args, **kwargs)


class loop(object):

    error_handler = None

    def __init__(self, flags=None, default=None):
        self._in_callback = False
        self._callbacks = []

        # self._check is a watcher that runs in each iteration of the
        # mainloop, just after the blocking call
        self._check = ffi.new("struct ev_check *")
        self._check_callback_ffi = _loop_callback("void(*)(struct ev_loop *, void*, int)",
                                                  self._check_callback,
                                                  onerror=self._check_callback_handle_error)
        libev.ev_check_init(self._check, self._check_callback_ffi)

        # self._prepare is a watcher that runs in each iteration of the mainloop,
        # just before the blocking call
        self._prepare = ffi.new("struct ev_prepare *")
        self._prepare_callback_ffi = _loop_callback("void(*)(struct ev_loop *, void*, int)",
                                                    self._run_callbacks,
                                                    onerror=self._check_callback_handle_error)
        libev.ev_prepare_init(self._prepare, self._prepare_callback_ffi)

        self._timer0 = ffi.new("struct ev_timer *")
        libev.ev_timer_init(self._timer0, libev.gevent_noop, 0.0, 0.0)

        c_flags = _flags_to_int(flags)
        _check_flags(c_flags)
        c_flags |= libev.EVFLAG_NOENV
        c_flags |= libev.EVFLAG_FORKCHECK
        if default is None:
            default = True
            if _default_loop_destroyed:
                default = False
        if default:
            self._ptr = libev.gevent_ev_default_loop(c_flags)
            if not self._ptr:
                raise SystemError("ev_default_loop(%s) failed" % (c_flags, ))

        else:
            self._ptr = libev.ev_loop_new(c_flags)
            if not self._ptr:
                raise SystemError("ev_loop_new(%s) failed" % (c_flags, ))
        if default or globals()["__SYSERR_CALLBACK"] is None:
            set_syserr_cb(self._handle_syserr)

        libev.ev_prepare_start(self._ptr, self._prepare)
        self.unref()
        libev.ev_check_start(self._ptr, self._check)
        self.unref()

        self._keepaliveset = set()

        if not _cffi_supports_on_error:
            if default:
                signalmodule.signal(2, self.int_handler)
            self.ate_keyboard_interrupt = False
            self.keyboard_interrupt_allowed = True

    def _check_callback_handle_error(self, t, v, tb):
        # None as the context argument causes the exception to be raised
        # in the main greenlet.
        self.handle_error(None, t, v, tb)

    if _cffi_supports_on_error:
        def _check_callback(self, *args):
            # If we have the onerror callback, this is a no-op; all the real
            # work to rethrow the exception is done by the onerror callback
            pass
    else:
        def _check_callback(self, *args):
            if self.ate_keyboard_interrupt:
                self.handle_error(self, KeyboardInterrupt, KeyboardInterrupt(), None)
                self.ate_keyboard_interrupt = False

        def int_handler(self, *args):
            if self.keyboard_interrupt_allowed:
                raise KeyboardInterrupt
            self.ate_keyboard_interrupt = True

    def _run_callbacks(self, evloop, _, revents):
        count = 1000
        libev.ev_timer_stop(self._ptr, self._timer0)
        while self._callbacks and count > 0:
            callbacks = self._callbacks
            self._callbacks = []
            for cb in callbacks:
                self.unref()
                callback = cb.callback
                args = cb.args
                if callback is None or args is None:
                    continue

                cb.callback = None

                try:
                    self.keyboard_interrupt_allowed = True
                    callback(*args)
                except:
                    self.handle_error(cb, *sys.exc_info())
                finally:
                    self.keyboard_interrupt_allowed = False
                    # Note, this must be reset here, because cb.args is used as a flag in callback class,
                    cb.args = None
                    count -= 1
        if self._callbacks:
            libev.ev_timer_start(self._ptr, self._timer0)

    def _stop_aux_watchers(self):
        if libev.ev_is_active(self._prepare):
            self.ref()
            libev.ev_prepare_stop(self._ptr, self._prepare)
        if libev.ev_is_active(self._check):
            self.ref()
            libev.ev_check_stop(self._ptr, self._check)

    def destroy(self):
        global _default_loop_destroyed
        if self._ptr:
            self._stop_aux_watchers()
            if globals()["__SYSERR_CALLBACK"] == self._handle_syserr:
                set_syserr_cb(None)
            if libev.ev_is_default_loop(self._ptr):
                _default_loop_destroyed = True
            libev.ev_loop_destroy(self._ptr)
            self._ptr = ffi.NULL
        # XXX restore default_int_signal handler if we set it (_cffi_supports_on_error is False)

    @property
    def ptr(self):
        return self._ptr

    @property
    def WatcherType(self):
        return watcher

    @property
    def MAXPRI(self):
        return libev.EV_MAXPRI

    @property
    def MINPRI(self):
        return libev.EV_MINPRI

    def _handle_syserr(self, message, errno):
        try:
            errno = os.strerror(errno)
        except:
            traceback.print_exc()
        try:
            message = '%s: %s' % (message, errno)
        except:
            traceback.print_exc()
        self.handle_error(None, SystemError, SystemError(message), None)

    def handle_error(self, context, type, value, tb):
        handle_error = None
        error_handler = self.error_handler
        if error_handler is not None:
            # we do want to do getattr every time so that setting Hub.handle_error property just works
            handle_error = getattr(error_handler, 'handle_error', error_handler)
            handle_error(context, type, value, tb)
        else:
            self._default_handle_error(context, type, value, tb)

    def _default_handle_error(self, context, type, value, tb):
        # note: Hub sets its own error handler so this is not used by gevent
        # this is here to make core.loop usable without the rest of gevent
        traceback.print_exception(type, value, tb)
        libev.ev_break(self._ptr, libev.EVBREAK_ONE)

    def run(self, nowait=False, once=False):
        flags = 0
        if nowait:
            flags |= libev.EVRUN_NOWAIT
        if once:
            flags |= libev.EVRUN_ONCE

        self.keyboard_interrupt_allowed = False
        libev.ev_run(self._ptr, flags)
        self.keyboard_interrupt_allowed = True

    def reinit(self):
        libev.ev_loop_fork(self._ptr)

    def ref(self):
        libev.ev_ref(self._ptr)

    def unref(self):
        libev.ev_unref(self._ptr)

    def break_(self, how=libev.EVBREAK_ONE):
        libev.ev_break(self._ptr, how)

    def verify(self):
        libev.ev_verify(self._ptr)

    def now(self):
        return libev.ev_now(self._ptr)

    def update(self):
        libev.ev_now_update(self._ptr)

    def __repr__(self):
        return '<%s at 0x%x %s>' % (self.__class__.__name__, id(self), self._format())

    @property
    def default(self):
        return True if libev.ev_is_default_loop(self._ptr) else False

    @property
    def iteration(self):
        return libev.ev_iteration(self._ptr)

    @property
    def depth(self):
        return libev.ev_depth(self._ptr)

    @property
    def backend_int(self):
        return libev.ev_backend(self._ptr)

    @property
    def backend(self):
        backend = libev.ev_backend(self._ptr)
        for key, value in _flags:
            if key == backend:
                return value
        return backend

    @property
    def pendingcnt(self):
        return libev.ev_pending_count(self._ptr)

    def io(self, fd, events, ref=True, priority=None):
        return io(self, fd, events, ref, priority)

    def timer(self, after, repeat=0.0, ref=True, priority=None):
        return timer(self, after, repeat, ref, priority)

    def signal(self, signum, ref=True, priority=None):
        return signal(self, signum, ref, priority)

    def idle(self, ref=True, priority=None):
        return idle(self, ref, priority)

    def prepare(self, ref=True, priority=None):
        return prepare(self, ref, priority)

    def check(self, ref=True, priority=None):
        return check(self, ref, priority)

    def fork(self, ref=True, priority=None):
        return fork(self, ref, priority)

    def async(self, ref=True, priority=None):
        return async(self, ref, priority)

    if sys.platform != "win32":

        def child(self, pid, trace=0, ref=True):
            return child(self, pid, trace, ref)

        def install_sigchld(self):
            libev.gevent_install_sigchld_handler()

    def stat(self, path, interval=0.0, ref=True, priority=None):
        return stat(self, path, interval, ref, priority)

    def callback(self, priority=None):
        return callback(self, priority)

    def run_callback(self, func, *args):
        cb = callback(func, args)
        self._callbacks.append(cb)
        self.ref()
        return cb

    def _format(self):
        if not self._ptr:
            return 'destroyed'
        msg = self.backend
        if self.default:
            msg += ' default'
        msg += ' pending=%s' % self.pendingcnt
        msg += self._format_details()
        return msg

    def _format_details(self):
        msg = ''
        fileno = self.fileno()
        try:
            activecnt = self.activecnt
        except AttributeError:
            activecnt = None
        if activecnt is not None:
            msg += ' ref=' + repr(activecnt)
        if fileno is not None:
            msg += ' fileno=' + repr(fileno)
        #if sigfd is not None and sigfd != -1:
        #    msg += ' sigfd=' + repr(sigfd)
        return msg

    def fileno(self):
        if self._ptr:
            fd = self._ptr.backend_fd
            if fd >= 0:
                return fd

    @property
    def activecnt(self):
        if not self._ptr:
            raise ValueError('operation on destroyed loop')
        return self._ptr.activecnt


class callback(object):

    __slots__ = ('callback', 'args')

    def __init__(self, callback, args):
        self.callback = callback
        self.args = args

    def stop(self):
        self.callback = None
        self.args = None

    # Note, that __nonzero__ and pending are different
    # nonzero is used in contexts where we need to know whether to schedule another callback,
    # so it's true if it's pending or currently running
    # 'pending' has the same meaning as libev watchers: it is cleared before entering callback

    def __nonzero__(self):
        # it's nonzero if it's pending or currently executing
        return self.args is not None
    __bool__ = __nonzero__

    @property
    def pending(self):
        return self.callback is not None

    def _format(self):
        return ''

    def __repr__(self):
        result = "<%s at 0x%x" % (self.__class__.__name__, id(self))
        if self.pending:
            result += " pending"
        if self.callback is not None:
            result += " callback=%r" % (self.callback, )
        if self.args is not None:
            result += " args=%r" % (self.args, )
        if self.callback is None and self.args is None:
            result += " stopped"
        return result + ">"


class watcher(object):

    def __init__(self, _loop, ref=True, priority=None, args=tuple()):
        self.loop = _loop
        if ref:
            self._flags = 0
        else:
            self._flags = 4
        self.args = None
        self._callback = None
        self._handle = ffi.new_handle(self)
        self._gwatcher = ffi.new('struct gevent_' + self._watcher_type + '*')
        self._watcher = ffi.addressof(self._gwatcher.watcher)
        self._gwatcher.handle = self._handle
        if priority is not None:
            libev.ev_set_priority(self._watcher, priority)
        self._watcher_init(self._watcher,
                           getattr(libev, '_gevent_' + self._watcher_type + '_callback'),
                           *args)

    # this is not needed, since we keep alive the watcher while it's started
    #def __del__(self):
    #    self._watcher_stop(self.loop._ptr, self._watcher)

    def __repr__(self):
        format = self._format()
        result = "<%s at 0x%x%s" % (self.__class__.__name__, id(self), format)
        if self.pending:
            result += " pending"
        if self.callback is not None:
            result += " callback=%r" % (self.callback, )
        if self.args is not None:
            result += " args=%r" % (self.args, )
        if self.callback is None and self.args is None:
            result += " stopped"
        return result + ">"

    def _format(self):
        return ''

    def _libev_unref(self):
        if self._flags & 6 == 4:
            self.loop.unref()
            self._flags |= 2

    def _get_ref(self):
        return False if self._flags & 4 else True

    def _set_ref(self, value):
        if value:
            if not self._flags & 4:
                return  # ref is already True
            if self._flags & 2:  # ev_unref was called, undo
                self.loop.ref()
            self._flags &= ~6  # do not want unref, no outstanding unref
        else:
            if self._flags & 4:
                return  # ref is already False
            self._flags |= 4
            if not self._flags & 2 and libev.ev_is_active(self._watcher):
                self.loop.unref()
                self._flags |= 2

    ref = property(_get_ref, _set_ref)

    def _get_callback(self):
        return self._callback

    def _set_callback(self, callback):
        if not callable(callback) and callback is not None:
            raise TypeError("Expected callable, not %r" % (callback, ))
        self._callback = callback
    callback = property(_get_callback, _set_callback)

    def start(self, callback, *args):
        if callback is None:
            raise TypeError('callback must be callable, not None')
        self.callback = callback
        self.args = args
        self._libev_unref()
        self._watcher_start(self.loop._ptr, self._watcher)
        self.loop._keepaliveset.add(self)

    def stop(self):
        if self._flags & 2:
            self.loop.ref()
            self._flags &= ~2
        self._watcher_stop(self.loop._ptr, self._watcher)
        self.loop._keepaliveset.discard(self)
        self._callback = None
        self.args = None

    def _get_priority(self):
        return libev.ev_priority(self._watcher)

    def _set_priority(self, priority):
        if libev.ev_is_active(self._watcher):
            raise AttributeError("Cannot set priority of an active watcher")
        libev.ev_set_priority(self._watcher, priority)

    priority = property(_get_priority, _set_priority)

    def feed(self, revents, callback, *args):
        self.callback = callback
        self.args = args
        if self._flags & 6 == 4:
            self.loop.unref()
            self._flags |= 2
        libev.ev_feed_event(self.loop._ptr, self._watcher, revents)
        if not self._flags & 1:
            # Py_INCREF(<PyObjectPtr>self)
            self._flags |= 1

    @property
    def active(self):
        return True if libev.ev_is_active(self._watcher) else False

    @property
    def pending(self):
        return True if libev.ev_is_pending(self._watcher) else False


class io(watcher):
    _watcher_start = libev.ev_io_start
    _watcher_stop = libev.ev_io_stop
    _watcher_init = libev.ev_io_init
    _watcher_type = 'ev_io'

    def __init__(self, loop, fd, events, ref=True, priority=None):
        if fd < 0:
            raise ValueError('fd must be non-negative: %r' % fd)
        if events & ~(libev.EV__IOFDSET | libev.EV_READ | libev.EV_WRITE):
            raise ValueError('illegal event mask: %r' % events)
        watcher.__init__(self, loop, ref=ref, priority=priority, args=(fd, events))

    def start(self, callback, *args, **kwargs):
        if kwargs.get('pass_events'):
            args = (GEVENT_CORE_EVENTS, ) + args
        super(io, self).start(callback, *args)

    def _get_fd(self):
        return libev.vfd_get(self._watcher.fd)

    def _set_fd(self, fd):
        if libev.ev_is_active(self._watcher):
            raise AttributeError("'io' watcher attribute 'fd' is read-only while watcher is active")
        vfd = libev.vfd_open(fd)
        libev.vfd_free(self._watcher.fd)
        libev.ev_io_init(self._watcher, self._cb, vfd, self._watcher.events)

    fd = property(_get_fd, _set_fd)

    def _get_events(self):
        return libev.vfd_get(self._watcher.fd)

    def _set_events(self, events):
        if libev.ev_is_active(self._watcher):
            raise AttributeError("'io' watcher attribute 'events' is read-only while watcher is active")
        libev.ev_io_init(self._watcher, self._cb, self._watcher.fd, events)

    events = property(_get_events, _set_events)

    @property
    def events_str(self):
        return _events_to_str(self._watcher.events)

    def _format(self):
        return ' fd=%s events=%s' % (self.fd, self.events_str)


class timer(watcher):
    _watcher_start = libev.ev_timer_start
    _watcher_stop = libev.ev_timer_stop
    _watcher_init = libev.ev_timer_init
    _watcher_type = 'ev_timer'

    def __init__(self, loop, after=0.0, repeat=0.0, ref=True, priority=None):
        if repeat < 0.0:
            raise ValueError("repeat must be positive or zero: %r" % repeat)
        watcher.__init__(self, loop, ref=ref, priority=priority, args=(after, repeat))

    def start(self, callback, *args, **kw):
        if callback is None:
            raise TypeError('callback must be callable, not None')
        update = kw.get("update", True)
        self.callback = callback
        self.args = args

        self._libev_unref()  # LIBEV_UNREF

        if update:
            libev.ev_now_update(self.loop._ptr)
        libev.ev_timer_start(self.loop._ptr, self._watcher)
        self.loop._keepaliveset.add(self)

    @property
    def at(self):
        return self._watcher.at

    def again(self, callback, *args, **kw):
        update = kw.get("update", True)
        self.callback = callback
        self.args = args
        self._libev_unref()
        if update:
            libev.ev_now_update(self.loop._ptr)
        libev.ev_timer_again(self.loop._ptr, self._watcher)


class signal(watcher):
    _watcher_start = libev.ev_signal_start
    _watcher_stop = libev.ev_signal_stop
    _watcher_init = libev.ev_signal_init
    _watcher_type = 'ev_signal'

    def __init__(self, loop, signalnum, ref=True, priority=None):
        if signalnum < 1 or signalnum >= signalmodule.NSIG:
            raise ValueError('illegal signal number: %r' % signalnum)
        # still possible to crash on one of libev's asserts:
        # 1) "libev: ev_signal_start called with illegal signal number"
        #    EV_NSIG might be different from signal.NSIG on some platforms
        # 2) "libev: a signal must not be attached to two different loops"
        #    we probably could check that in LIBEV_EMBED mode, but not in general
        watcher.__init__(self, loop, ref=ref, priority=priority, args=(signalnum, ))


class idle(watcher):
    _watcher_start = libev.ev_idle_start
    _watcher_stop = libev.ev_idle_stop
    _watcher_init = libev.ev_idle_init
    _watcher_type = 'ev_idle'


class prepare(watcher):
    _watcher_start = libev.ev_prepare_start
    _watcher_stop = libev.ev_prepare_stop
    _watcher_init = libev.ev_prepare_init
    _watcher_type = 'ev_prepare'


class check(watcher):
    _watcher_start = libev.ev_check_start
    _watcher_stop = libev.ev_check_stop
    _watcher_init = libev.ev_check_init
    _watcher_type = 'ev_check'


class fork(watcher):
    _watcher_start = libev.ev_fork_start
    _watcher_stop = libev.ev_fork_stop
    _watcher_init = libev.ev_fork_init
    _watcher_type = 'ev_fork'


class async(watcher):
    _watcher_start = libev.ev_async_start
    _watcher_stop = libev.ev_async_stop
    _watcher_init = libev.ev_async_init
    _watcher_type = 'ev_async'

    def send(self):
        libev.ev_async_send(self.loop._ptr, self._watcher)

    @property
    def pending(self):
        return True if libev.ev_async_pending(self._watcher) else False


class child(watcher):
    _watcher_start = libev.ev_child_start
    _watcher_stop = libev.ev_child_stop
    _watcher_init = libev.ev_child_init
    _watcher_type = 'ev_child'

    def __init__(self, loop, pid, trace=0, ref=True):
        if not loop.default:
            raise TypeError('child watchers are only available on the default loop')
        loop.install_sigchld()
        watcher.__init__(self, loop, ref=ref, args=(pid, trace))

    def _format(self):
        return ' pid=%r rstatus=%r' % (self.pid, self.rstatus)

    @property
    def pid(self):
        return self._watcher.pid

    @property
    def rpid(self, ):
        return self._watcher.rpid

    @rpid.setter
    def rpid(self, value):
        self._watcher.rpid = value

    @property
    def rstatus(self):
        return self._watcher.rstatus

    @rstatus.setter
    def rstatus(self, value):
        self._watcher.rstatus = value


class stat(watcher):
    _watcher_start = libev.ev_stat_start
    _watcher_stop = libev.ev_stat_stop
    _watcher_init = libev.ev_stat_init
    _watcher_type = 'ev_stat'

    def __init__(self, _loop, path, interval=0.0, ref=True, priority=None):
        if not isinstance(path, bytes):
            # XXX: Filesystem encoding? Python itself has issues here, were they fixed?
            path = path.encode('utf-8')

        watcher.__init__(self, _loop, ref=ref, priority=priority,
                         # cffi doesn't automatically marshal byte strings to
                         # char* in the function call; instead it passes an
                         # empty string or garbage pointer. If the watcher's
                         # path is incorrect, watching silently fails
                         # (the underlying call to lstat() keeps erroring out)
                         args=(ffi.new('char[]', path),
                               interval))

    @property
    def path(self):
        return ffi.string(self._watcher.path)

    @property
    def attr(self):
        if not self._watcher.attr.st_nlink:
            return
        return self._watcher.attr

    @property
    def prev(self):
        if not self._watcher.prev.st_nlink:
            return
        return self._watcher.prev

    @property
    def interval(self):
        return self._watcher.interval


def _syserr_cb(msg):
    try:
        msg = ffi.string(msg)
        __SYSERR_CALLBACK(msg, ffi.errno)
    except:
        set_syserr_cb(None)
        raise  # let cffi print the traceback

_syserr_cb._cb = ffi.callback("void(*)(char *msg)", _syserr_cb)


def set_syserr_cb(callback):
    global __SYSERR_CALLBACK
    if callback is None:
        libev.ev_set_syserr_cb(ffi.NULL)
        __SYSERR_CALLBACK = None
    elif callable(callback):
        libev.ev_set_syserr_cb(_syserr_cb._cb)
        __SYSERR_CALLBACK = callback
    else:
        raise TypeError('Expected callable or None, got %r' % (callback, ))

__SYSERR_CALLBACK = None

LIBEV_EMBED = True
