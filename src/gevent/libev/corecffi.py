# pylint:disable=too-many-lines, protected-access, redefined-outer-name, not-callable,
# pylint:disable=no-member
from __future__ import absolute_import, print_function
import sys
import os
import traceback
import signal as signalmodule

# pylint:disable=undefined-all-variable
__all__ = [
    'get_version',
    'get_header_version',
    'supported_backends',
    'recommended_backends',
    'embeddable_backends',
    'time',
    'loop',
]

import gevent.libev._corecffi as _corecffi # pylint:disable=no-name-in-module

ffi = _corecffi.ffi # pylint:disable=no-member
libev = _corecffi.lib # pylint:disable=no-member

if hasattr(libev, 'vfd_open'):
    # Must be on windows
    assert sys.platform.startswith("win"), "vfd functions only needed on windows"
    vfd_open = libev.vfd_open
    vfd_free = libev.vfd_free
    vfd_get = libev.vfd_get
else:
    vfd_open = vfd_free = vfd_get = lambda fd: fd

#####
## NOTE on Windows:
# The C implementation does several things specially for Windows;
# a possibly incomplete list is:
#
# - the loop runs a periodic signal checker;
# - the io watcher constructor is different and it has a destructor;
# - the child watcher is not defined
#
# The CFFI implementation does none of these things, and so
# is possibly NOT FUNCTIONALLY CORRECT on Win32
#####

#####
## Note on CFFI objects, callbacks and the lifecycle of watcher objects
#
# Each subclass of `watcher` allocates a C structure of the
# appropriate type e.g., struct gevent_ev_io and holds this pointer in
# its `_gwatcher` attribute. When that watcher instance is garbage
# collected, then the C structure is also freed. The C structure is
# passed to libev from the watcher's start() method and then to the
# appropriate C callback function, e.g., _gevent_ev_io_callback, which
# passes it back to python's _python_callback where we need the
# watcher instance. Therefore, as long as that callback is active (the
# watcher is started), the watcher instance must not be allowed to get
# GC'd---any access at the C level or even the FFI level to the freed
# memory could crash the process.
#
# However, the typical idiom calls for writing something like this:
#  loop.io(fd, python_cb).start()
# thus forgetting the newly created watcher subclass and allowing it to be immediately
# GC'd. To combat this, when the watcher is started, it places itself into the loop's
# `_keepaliveset`, and it only removes itself when the watcher's `stop()` method is called.
# Often, this is the *only* reference keeping the watcher object, and hence its C structure,
# alive.
#
# This is slightly complicated by the fact that the python-level
# callback, called from the C callback, could choose to manually stop
# the watcher. When we return to the C level callback, we now have an
# invalid pointer, and attempting to pass it back to Python (e.g., to
# handle an error) could crash. Hence, _python_callback,
# _gevent_io_callback, and _python_handle_error cooperate to make sure
# that the watcher instance stays in the loops `_keepaliveset` while
# the C code could be running---and if it gets removed, to not call back
# to Python again.
# See also https://github.com/gevent/gevent/issues/676
####


@ffi.callback("int(void* handle, int revents)")
def _python_callback(handle, revents):
    """
    Returns an integer having one of three values:

    - -1
      An exception occurred during the callback and you must call
      :func:`_python_handle_error` to deal with it. The Python watcher
      object will have the exception tuple saved in ``_exc_info``.
    - 0
      Everything went according to plan. You should check to see if the libev
      watcher is still active, and call :func:`_python_stop` if so. This will
      clean up the memory.
    - 1
      Everything went according to plan, but the watcher has already
      been stopped. Its memory may no longer be valid.
    """
    try:
        # Even dereferencing the handle needs to be inside the try/except;
        # if we don't return normally (e.g., a signal) then we wind up going
        # to the 'onerror' handler, which
        # is not what we want; that can permanently wedge the loop depending
        # on which callback was executing
        the_watcher = ffi.from_handle(handle)
        args = the_watcher.args
        if args is None:
            # Legacy behaviour from corecext: convert None into ()
            # See test__core_watcher.py
            args = _NOARGS
        if args and args[0] == GEVENT_CORE_EVENTS:
            args = (revents, ) + args[1:]
        the_watcher.callback(*args)
    except: # pylint:disable=bare-except
        the_watcher._exc_info = sys.exc_info()
        # Depending on when the exception happened, the watcher
        # may or may not have been stopped. We need to make sure its
        # memory stays valid so we can stop it at the ev level if needed.
        the_watcher.loop._keepaliveset.add(the_watcher)
        return -1
    else:
        if the_watcher in the_watcher.loop._keepaliveset:
            # It didn't stop itself
            return 0
        return 1 # It stopped itself
libev.python_callback = _python_callback


@ffi.callback("void(void* handle, int revents)")
def _python_handle_error(handle, revents):
    try:
        watcher = ffi.from_handle(handle)
        exc_info = watcher._exc_info
        del watcher._exc_info
        watcher.loop.handle_error(watcher, *exc_info)
    finally:
        # XXX Since we're here on an error condition, and we
        # made sure that the watcher object was put in loop._keepaliveset,
        # what about not stopping the watcher? Looks like a possible
        # memory leak?
        if revents & (libev.EV_READ | libev.EV_WRITE):
            try:
                watcher.stop()
            except: # pylint:disable=bare-except
                watcher.loop.handle_error(watcher, *sys.exc_info())
            return # pylint:disable=lost-exception
libev.python_handle_error = _python_handle_error


@ffi.callback("void(void* handle)")
def _python_stop(handle):
    watcher = ffi.from_handle(handle)
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
    return 'libev-%d.%02d' % (libev.ev_version_major(), libev.ev_version_minor())


def get_header_version():
    return 'libev-%d.%02d' % (libev.EV_VERSION_MAJOR, libev.EV_VERSION_MINOR)

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
    integer_types = (int,)
else:
    import __builtin__ # pylint:disable=import-error
    basestring = __builtin__.basestring,
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
    if not flags & libev.EVBACKEND_ALL:
        raise ValueError('Invalid value for backend: 0x%x' % flags)
    if not flags & libev.ev_supported_backends():
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
    return libev.ev_time()

_default_loop_destroyed = False


def _loop_callback(*args, **kwargs):
    return ffi.callback(*args, **kwargs)


class loop(object):
    # pylint:disable=too-many-public-methods

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

        # A timer we start and stop on demand. If we have callbacks,
        # too many to run in one iteration of _run_callbacks, we turn this
        # on so as to have the next iteration of the run loop return to us
        # as quickly as possible.
        # TODO: There may be a more efficient way to do this using ev_timer_again;
        # see the "ev_timer" section of the ev manpage (http://linux.die.net/man/3/ev)
        self._timer0 = ffi.new("struct ev_timer *")
        libev.ev_timer_init(self._timer0, libev.gevent_noop, 0.0, 0.0)

        # TODO: We may be able to do something nicer and use the existing python_callback
        # combined with onerror and the class check/timer/prepare to simplify things
        # and unify our handling

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

    def _check_callback_handle_error(self, t, v, tb):
        # None as the context argument causes the exception to be raised
        # in the main greenlet.
        self.handle_error(None, t, v, tb)

    def _check_callback(self, *args):
        # If we have the onerror callback, this is a no-op; all the real
        # work to rethrow the exception is done by the onerror callback
        pass

    def _run_callbacks(self, _evloop, _, _revents):
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
                    # it's been stopped
                    continue

                cb.callback = None

                try:
                    callback(*args)
                except: # pylint:disable=bare-except
                    # If we allow an exception to escape this method (while we are running the ev callback),
                    # then CFFI will print the error and libev will continue executing.
                    # There are two problems with this. The first is that the code after
                    # the loop won't run. The second is that any remaining callbacks scheduled
                    # for this loop iteration will be silently dropped; they won't run, but they'll
                    # also not be *stopped* (which is not a huge deal unless you're looking for
                    # consistency or checking the boolean/pending status; the loop doesn't keep
                    # a reference to them like it does to watchers...*UNLESS* the callback itself had
                    # a reference to a watcher; then I don't know what would happen, it depends on
                    # the state of the watcher---a leak or crash is not totally inconceivable).
                    # The Cython implementation in core.ppyx uses gevent_call from callbacks.c
                    # to run the callback, which uses gevent_handle_error to handle any errors the
                    # Python callback raises...it unconditionally simply prints any error raised
                    # by loop.handle_error and clears it, so callback handling continues.
                    # We take a similar approach (but are extra careful about printing)
                    try:
                        self.handle_error(cb, *sys.exc_info())
                    except: # pylint:disable=bare-except
                        try:
                            print("Exception while handling another error", file=sys.stderr)
                            traceback.print_exc()
                        except: # pylint:disable=bare-except
                            pass # Nothing we can do here
                finally:
                    # NOTE: this must be reset here, because cb.args is used as a flag in
                    # the callback class so that bool(cb) of a callback that has been run
                    # becomes False
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
        except: # pylint:disable=bare-except
            traceback.print_exc()
        try:
            message = '%s: %s' % (message, errno)
        except: # pylint:disable=bare-except
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

    def _default_handle_error(self, context, type, value, tb): # pylint:disable=unused-argument
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

        libev.ev_run(self._ptr, flags)

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

        def reset_sigchld(self):
            libev.gevent_reset_sigchld_handler()

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

# For times when *args is captured but often not passed (empty),
# we can avoid keeping the new tuple that was created for *args
# around by using a constant.
_NOARGS = ()


class callback(object):

    __slots__ = ('callback', 'args')

    def __init__(self, callback, args):
        self.callback = callback
        self.args = args or _NOARGS

    def stop(self):
        self.callback = None
        self.args = None

    # Note that __nonzero__ and pending are different
    # bool() is used in contexts where we need to know whether to schedule another callback,
    # so it's true if it's pending or currently running
    # 'pending' has the same meaning as libev watchers: it is cleared before actually
    # running the callback

    def __nonzero__(self):
        # it's nonzero if it's pending or currently executing
        # NOTE: This depends on loop._run_callbacks setting the args property
        # to None.
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

    def __init__(self, _loop, ref=True, priority=None, args=_NOARGS):
        self.loop = _loop
        if ref:
            self._flags = 0
        else:
            self._flags = 4
        self._args = None
        self._callback = None
        self._handle = ffi.new_handle(self)

        self._watcher = ffi.new(self._watcher_struct_pointer_type)
        self._watcher.data = self._handle
        if priority is not None:
            libev.ev_set_priority(self._watcher, priority)
        self._watcher_init(self._watcher,
                           self._watcher_callback,
                           *args)

    # A string identifying the type of libev object we watch, e.g., 'ev_io'
    # This should be a class attribute.
    _watcher_type = None
    # A class attribute that is the callback on the libev object that init's the C struct,
    # e.g., libev.ev_io_init. If None, will be set by _init_subclasses.
    _watcher_init = None
    # A class attribute that is the callback on the libev object that starts the C watcher,
    # e.g., libev.ev_io_start. If None, will be set by _init_subclasses.
    _watcher_start = None
    # A class attribute that is the callback on the libev object that stops the C watcher,
    # e.g., libev.ev_io_stop. If None, will be set by _init_subclasses.
    _watcher_stop = None
    # A cffi ctype object identifying the struct pointer we create.
    # This is a class attribute set based on the _watcher_type
    _watcher_struct_pointer_type = None
    # The attribute of the libev object identifying the custom
    # callback function for this type of watcher. This is a class
    # attribute set based on the _watcher_type in _init_subclasses.
    _watcher_callback = None

    @classmethod
    def _init_subclasses(cls):
        for subclass in cls.__subclasses__(): # pylint:disable=no-member
            watcher_type = subclass._watcher_type
            subclass._watcher_struct_pointer_type = ffi.typeof('struct ' + watcher_type + '*')
            subclass._watcher_callback = ffi.addressof(libev,
                                                       '_gevent_generic_callback')
            for name in 'start', 'stop', 'init':
                ev_name = watcher_type + '_' + name
                watcher_name = '_watcher' + '_' + name
                if getattr(subclass, watcher_name) is None:
                    setattr(subclass, watcher_name,
                            getattr(libev, ev_name))

    # this is not needed, since we keep alive the watcher while it's started
    #def __del__(self):
    #    self._watcher_stop(self.loop._ptr, self._watcher)

    def __repr__(self):
        formats = self._format()
        result = "<%s at 0x%x%s" % (self.__class__.__name__, id(self), formats)
        if self.pending:
            result += " pending"
        if self.callback is not None:
            result += " callback=%r" % (self.callback, )
        if self.args is not None:
            result += " args=%r" % (self.args, )
        if self.callback is None and self.args is None:
            result += " stopped"
        result += " handle=%s" % (self._watcher.data)
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

    def _set_callback(self, cb):
        if not callable(cb) and cb is not None:
            raise TypeError("Expected callable, not %r" % (cb, ))
        self._callback = cb
    callback = property(_get_callback, _set_callback)

    def _get_args(self):
        return self._args

    def _set_args(self, args):
        if not isinstance(args, tuple) and args is not None:
            raise TypeError("args must be a tuple or None")
        self._args = args

    args = property(_get_args, _set_args)

    def start(self, callback, *args):
        if callback is None:
            raise TypeError('callback must be callable, not None')
        self.callback = callback
        self.args = args or _NOARGS
        self._libev_unref()
        self.loop._keepaliveset.add(self)
        self._watcher_start(self.loop._ptr, self._watcher)

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
        self.args = args or _NOARGS
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
    _watcher_type = 'ev_io'

    def __init__(self, loop, fd, events, ref=True, priority=None):
        # XXX: Win32: Need to vfd_open the fd and free the old one?
        # XXX: Win32: Need a destructor to free the old fd?
        if fd < 0:
            raise ValueError('fd must be non-negative: %r' % fd)
        if events & ~(libev.EV__IOFDSET | libev.EV_READ | libev.EV_WRITE):
            raise ValueError('illegal event mask: %r' % events)
        watcher.__init__(self, loop, ref=ref, priority=priority, args=(fd, events))

    def start(self, callback, *args, **kwargs):
        # pylint:disable=arguments-differ
        args = args or _NOARGS
        if kwargs.get('pass_events'):
            args = (GEVENT_CORE_EVENTS, ) + args
        watcher.start(self, callback, *args)

    def _get_fd(self):
        return vfd_get(self._watcher.fd)

    def _set_fd(self, fd):
        if libev.ev_is_active(self._watcher):
            raise AttributeError("'io' watcher attribute 'fd' is read-only while watcher is active")
        vfd = vfd_open(fd)
        vfd_free(self._watcher.fd)
        self._watcher_init(self._watcher, self._watcher_callback, vfd, self._watcher.events)

    fd = property(_get_fd, _set_fd)

    def _get_events(self):
        return self._watcher.events

    def _set_events(self, events):
        if libev.ev_is_active(self._watcher):
            raise AttributeError("'io' watcher attribute 'events' is read-only while watcher is active")
        self._watcher_init(self._watcher, self._watcher_callback, self._watcher.fd, events)

    events = property(_get_events, _set_events)

    @property
    def events_str(self):
        return _events_to_str(self._watcher.events)

    def _format(self):
        return ' fd=%s events=%s' % (self.fd, self.events_str)


class timer(watcher):
    _watcher_type = 'ev_timer'

    def __init__(self, loop, after=0.0, repeat=0.0, ref=True, priority=None):
        if repeat < 0.0:
            raise ValueError("repeat must be positive or zero: %r" % repeat)
        watcher.__init__(self, loop, ref=ref, priority=priority, args=(after, repeat))

    def start(self, callback, *args, **kw):
        # pylint:disable=arguments-differ
        update = kw.get("update", True)
        if update:
            # Quoth the libev doc: "This is a costly operation and is
            # usually done automatically within ev_run(). This
            # function is rarely useful, but when some event callback
            # runs for a very long time without entering the event
            # loop, updating libev's idea of the current time is a
            # good idea."
            # So do we really need to default to true?
            libev.ev_now_update(self.loop._ptr)
        watcher.start(self, callback, *args)

    @property
    def at(self):
        return self._watcher.at

    def again(self, callback, *args, **kw):
        # Exactly the same as start(), just with a different initializer
        # function
        self._watcher_start = libev.ev_timer_again
        try:
            self.start(callback, *args, **kw)
        finally:
            del self._watcher_start


class signal(watcher):
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
    _watcher_type = 'ev_idle'


class prepare(watcher):
    _watcher_type = 'ev_prepare'


class check(watcher):
    _watcher_type = 'ev_check'


class fork(watcher):
    _watcher_type = 'ev_fork'


class async(watcher):
    _watcher_type = 'ev_async'

    def send(self):
        libev.ev_async_send(self.loop._ptr, self._watcher)

    @property
    def pending(self):
        return True if libev.ev_async_pending(self._watcher) else False


class child(watcher):
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
    _watcher_type = 'ev_stat'

    @staticmethod
    def _encode_path(path):
        if isinstance(path, bytes):
            return path

        # encode for the filesystem. Not all systems (e.g., Unix)
        # will have an encoding specified
        encoding = sys.getfilesystemencoding() or 'utf-8'
        try:
            path = path.encode(encoding, 'surrogateescape')
        except LookupError:
            # Can't encode it, and the error handler doesn't
            # exist. Probably on Python 2 with an astral character.
            # Not sure how to handle this.
            raise UnicodeEncodeError("Can't encode path to filesystem encoding")
        return path

    def __init__(self, _loop, path, interval=0.0, ref=True, priority=None):
        # Store the encoded path in the same attribute that corecext does
        self._paths = self._encode_path(path)

        # Keep the original path to avoid re-encoding, especially on Python 3
        self._path = path

        # Although CFFI would automatically convert a bytes object into a char* when
        # calling ev_stat_init(..., char*, ...), on PyPy the char* pointer is not
        # guaranteed to live past the function call. On CPython, only with a constant/interned
        # bytes object is the pointer guaranteed to last path the function call. (And since
        # Python 3 is pretty much guaranteed to produce a newly-encoded bytes object above, thats
        # rarely the case). Therefore, we must keep a reference to the produced cdata object
        # so that the struct ev_stat_watcher's `path` pointer doesn't become invalid/deallocated
        self._cpath = ffi.new('char[]', self._paths)

        watcher.__init__(self, _loop, ref=ref, priority=priority,
                         args=(self._cpath,
                               interval))

    @property
    def path(self):
        return self._path

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

# All watcher subclasses must be declared above. Now we do some
# initialization; this is not only a minor optimization, it protects
# against later runtime typos and attribute errors
watcher._init_subclasses()


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
