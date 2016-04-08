"""
Basic loop implementation for ffi-based cores.
"""
# pylint: disable=too-many-lines, protected-access, redefined-outer-name, not-callable
from __future__ import absolute_import, print_function
import sys
import os
import traceback

from gevent._ffi.callback import callback

__all__ = [
    'AbstractLoop',
    'assign_standard_callbacks',
]


class _EVENTSType(object):
    def __repr__(self):
        return 'gevent.core.EVENTS'

EVENTS = GEVENT_CORE_EVENTS = _EVENTSType()


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
class _Callbacks(object):

    def __init__(self, ffi):
        self.ffi = ffi
        self.callbacks = []

    def python_callback(self, handle, revents):
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
            the_watcher = self.ffi.from_handle(handle)
            args = the_watcher.args
            if args is None:
                # Legacy behaviour from corecext: convert None into ()
                # See test__core_watcher.py
                args = _NOARGS
            if len(args) > 0 and args[0] == GEVENT_CORE_EVENTS:
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

    def python_handle_error(self, handle, _revents):
        try:
            watcher = self.ffi.from_handle(handle)
            exc_info = watcher._exc_info
            del watcher._exc_info
            watcher.loop.handle_error(watcher, *exc_info)
        finally:
            # XXX Since we're here on an error condition, and we
            # made sure that the watcher object was put in loop._keepaliveset,
            # what about not stopping the watcher? Looks like a possible
            # memory leak?
            # XXX: This used to do "if revents & (libev.EV_READ | libev.EV_WRITE)"
            # before stopping. Why?
            try:
                watcher.stop()
            except: # pylint:disable=bare-except
                watcher.loop.handle_error(watcher, *sys.exc_info())
            return # pylint:disable=lost-exception

    def python_stop(self, handle):
        watcher = self.ffi.from_handle(handle)
        watcher.stop()


def assign_standard_callbacks(ffi, lib):
    # ns keeps these cdata objects alive at the python level
    callbacks = _Callbacks(ffi)
    for sig, func in (("int(void* handle, int revents)", callbacks.python_callback),
                      ("void(void* handle, int revents)", callbacks.python_handle_error),
                      ("void(void* handle)", callbacks.python_stop)):
        callback = ffi.callback(sig)(func)
        # keep alive the cdata
        callbacks.callbacks.append(callback)
        # pass to the library C variable
        setattr(lib, func.__name__, callback)

    return callbacks


if sys.version_info[0] >= 3:
    basestring = (bytes, str)
    integer_types = int,
else:
    import __builtin__ # pylint:disable=import-error
    basestring = __builtin__.basestring,
    integer_types = (int, __builtin__.long)



_default_loop_destroyed = False


def _loop_callback(ffi, *args, **kwargs):
    return ffi.callback(*args, **kwargs)

_NOARGS = ()

class AbstractLoop(object):
    # pylint:disable=too-many-public-methods

    error_handler = None

    _CHECK_POINTER = None
    _CHECK_CALLBACK_SIG = None

    _TIMER_POINTER = None
    _TIMER_CALLBACK_SIG = None

    _PREPARE_POINTER = None
    _PREPARE_CALLBACK_SIG = None

    def __init__(self, ffi, lib, watchers, flags=None, default=None):
        self._ffi = ffi
        self._lib = lib
        self._watchers = watchers
        self._in_callback = False
        self._callbacks = []
        self._keepaliveset = set()

        self._ptr = self._init_loop(flags, default)

        # self._check is a watcher that runs in each iteration of the
        # mainloop, just after the blocking call
        self._check = ffi.new(self._CHECK_POINTER)
        self._check_callback_ffi = _loop_callback(ffi,
                                                  self._CHECK_CALLBACK_SIG,
                                                  self._check_callback,
                                                  onerror=self._check_callback_handle_error)
        self._init_and_start_check()

        # self._prepare is a watcher that runs in each iteration of the mainloop,
        # just before the blocking call
        self._prepare = ffi.new(self._PREPARE_POINTER)
        self._prepare_callback_ffi = _loop_callback(ffi,
                                                    self._PREPARE_CALLBACK_SIG,
                                                    self._run_callbacks,
                                                    onerror=self._check_callback_handle_error)
        self._init_and_start_prepare()

        # A timer we start and stop on demand. If we have callbacks,
        # too many to run in one iteration of _run_callbacks, we turn this
        # on so as to have the next iteration of the run loop return to us
        # as quickly as possible.
        # TODO: There may be a more efficient way to do this using ev_timer_again;
        # see the "ev_timer" section of the ev manpage (http://linux.die.net/man/3/ev)
        self._timer0 = ffi.new(self._TIMER_POINTER)
        self._init_callback_timer()

        # TODO: We may be able to do something nicer and use the existing python_callback
        # combined with onerror and the class check/timer/prepare to simplify things
        # and unify our handling

    def _init_loop(self, flags, default):
        """
        Called by __init__ to create or find the loop. The return value
        is assigned to self._ptr.
        """
        raise NotImplementedError()

    def _init_and_start_check(self):
        raise NotImplementedError()

    def _init_and_start_prepare(self):
        raise NotImplementedError()

    def _init_callback_timer(self):
        raise NotImplementedError()

    def _stop_callback_timer(self):
        raise NotImplementedError()

    def _start_callback_timer(self):
        raise NotImplementedError()

    def _check_callback_handle_error(self, t, v, tb):
        # None as the context argument causes the exception to be raised
        # in the main greenlet.
        self.handle_error(None, t, v, tb)

    def _check_callback(self, *args):
        # If we have the onerror callback, this is a no-op; all the real
        # work to rethrow the exception is done by the onerror callback
        pass

    def _run_callbacks(self, *args):
        count = 1000
        self._stop_callback_timer()
        while self._callbacks and count > 0:
            callbacks = self._callbacks
            self._callbacks = []
            for cb in callbacks:
                self.unref() # XXX: libuv doesn't have a global ref count!
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
            self._start_callback_timer()

    def _stop_aux_watchers(self):
        raise NotImplementedError()

    def destroy(self):
        if self._ptr:
            self._stop_aux_watchers()
            self._ptr = self._ffi.NULL

    @property
    def ptr(self):
        return self._ptr

    @property
    def WatcherType(self):
        return self._watchers.watcher

    @property
    def MAXPRI(self):
        return 1

    @property
    def MINPRI(self):
        return 1

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
        # Should cause the loop to stop running.
        traceback.print_exception(type, value, tb)


    def run(self, nowait=False, once=False):
        raise NotImplementedError()

    def reinit(self):
        raise NotImplementedError()

    def ref(self):
        # XXX: libuv doesn't do it this way
        raise NotImplementedError()

    def unref(self):
        raise NotImplementedError()

    def break_(self, how=None):
        raise NotImplementedError()

    def verify(self):
        pass

    def now(self):
        raise NotImplementedError()

    def update(self):
        raise NotImplementedError()

    def __repr__(self):
        return '<%s at 0x%x %s>' % (self.__class__.__name__, id(self), self._format())

    @property
    def default(self):
        pass

    @property
    def iteration(self):
        return -1

    @property
    def depth(self):
        return -1

    @property
    def backend_int(self):
        return 0

    @property
    def backend(self):
        return "<default backend>"

    @property
    def pendingcnt(self):
        return 0

    def io(self, fd, events, ref=True, priority=None):
        return self._watchers.io(self, fd, events, ref, priority)

    def timer(self, after, repeat=0.0, ref=True, priority=None):
        return self._watchers.timer(self, after, repeat, ref, priority)

    def signal(self, signum, ref=True, priority=None):
        return self._watchers.signal(self, signum, ref, priority)

    def idle(self, ref=True, priority=None):
        return self._watchers.idle(self, ref, priority)

    def prepare(self, ref=True, priority=None):
        return self._watchers.prepare(self, ref, priority)

    def check(self, ref=True, priority=None):
        return self._watchers.check(self, ref, priority)

    def fork(self, ref=True, priority=None):
        return self._watchers.fork(self, ref, priority)

    def async(self, ref=True, priority=None):
        return self._watchers.async(self, ref, priority)

    if sys.platform != "win32":

        def child(self, pid, trace=0, ref=True):
            return self._watchers.child(self, pid, trace, ref)

        def install_sigchld(self):
            pass

    def stat(self, path, interval=0.0, ref=True, priority=None):
        return self._watchers.stat(self, path, interval, ref, priority)

    def callback(self, priority=None):
        return callback(self, priority)

    def _setup_for_run_callback(self):
        raise NotImplementedError()

    def run_callback(self, func, *args):
        cb = callback(func, args)
        self._callbacks.append(cb)
        self._setup_for_run_callback()

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
        return None

    @property
    def activecnt(self):
        if not self._ptr:
            raise ValueError('operation on destroyed loop')
        return 0
