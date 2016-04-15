"""
libuv loop implementation
"""

from __future__ import absolute_import, print_function

import os
from collections import defaultdict
from collections import namedtuple
import signal
from weakref import WeakValueDictionary


from gevent._ffi.loop import AbstractLoop
from gevent.libuv import _corecffi # pylint:disable=no-name-in-module,import-error
from gevent._ffi.loop import assign_standard_callbacks

ffi = _corecffi.ffi
libuv = _corecffi.lib

__all__ = [
]

_callbacks = assign_standard_callbacks(ffi, libuv)

from gevent._ffi.loop import EVENTS
GEVENT_CORE_EVENTS = EVENTS # export

from gevent.libuv import watcher as _watchers

_events_to_str = _watchers._events_to_str # export

READ = libuv.UV_READABLE
WRITE = libuv.UV_WRITABLE

def get_version():
    uv_bytes = ffi.string(libuv.uv_version_string())
    if not isinstance(uv_bytes, str):
        # Py3
        uv_str = uv_bytes.decode("ascii")
    else:
        uv_str = uv_bytes

    return 'libuv-' + uv_str

def get_header_version():
    return 'libuv-%d.%d.%d' % (libuv.UV_VERSION_MAJOR, libuv.UV_VERSION_MINOR, libuv.UV_VERSION_PATCH)

def supported_backends():
    return ['default']

class loop(AbstractLoop):

    DEFAULT_LOOP_REGENERATES = True

    error_handler = None

    _CHECK_POINTER = 'uv_check_t *'
    _CHECK_CALLBACK_SIG = "void(*)(void*)"

    _PREPARE_POINTER = 'uv_prepare_t *'
    _PREPARE_CALLBACK_SIG = "void(*)(void*)"

    _TIMER_POINTER = 'uv_timer_t *'

    def __init__(self, flags=None, default=None):
        AbstractLoop.__init__(self, ffi, libuv, _watchers, flags, default)
        self.__loop_pid = os.getpid()
        self._child_watchers = defaultdict(list)
        self._io_watchers = WeakValueDictionary()

    def _init_loop(self, flags, default):
        if default is None:
            default = True
            # Unlike libev, libuv creates a new default
            # loop automatically if the old default loop was
            # closed.

        if default:
            ptr = libuv.uv_default_loop()
        else:
            ptr = libuv.uv_loop_new()


        if not ptr:
            raise SystemError("Failed to get loop")
        return ptr

    _signal_idle = None

    def _init_and_start_check(self):
        libuv.uv_check_init(self._ptr, self._check)
        libuv.uv_check_start(self._check, self._check_callback_ffi)
        libuv.uv_unref(self._check)

        # We also have to have an idle watcher to be able to handle
        # signals in a timely manner. Without them, libuv won't loop again
        # and call into its check and prepare handlers.
        # Note that this basically forces us into a busy-loop
        # XXX: As predicted, using an idle watcher causes our process
        # to eat 100% CPU time. We instead use a timer with a max of a 1 second
        # delay to notice signals.
        # XXX: Perhaps we could optimize this to notice when there are other
        # timers in the loop and start/stop it then
        self._signal_idle = ffi.new("uv_timer_t*")
        libuv.uv_timer_init(self._ptr, self._signal_idle)
        libuv.uv_timer_start(self._signal_idle, self._check_callback_ffi,
                             1000,
                             1000)
        libuv.uv_unref(self._signal_idle)

    def _init_and_start_prepare(self):
        libuv.uv_prepare_init(self._ptr, self._prepare)
        libuv.uv_prepare_start(self._prepare, self._prepare_callback_ffi)
        libuv.uv_unref(self._prepare)

    def _init_callback_timer(self):
        libuv.uv_timer_init(self._ptr, self._timer0)

    def _stop_callback_timer(self):
        libuv.uv_timer_stop(self._timer0)

    def _start_callback_timer(self):
        libuv.uv_timer_start(self._timer0, libuv.gevent_noop, 0, 0)

    def _stop_aux_watchers(self):
        libuv.uv_prepare_stop(self._prepare)
        libuv.uv_ref(self._prepare) # Why are we doing this?
        libuv.uv_check_stop(self._check)
        libuv.uv_ref(self._check)

        libuv.uv_timer_stop(self._signal_idle)
        libuv.uv_ref(self._signal_idle)

    def _setup_for_run_callback(self):
        self._start_callback_timer()
        libuv.uv_ref(self._timer0)

    def destroy(self):
        if self._ptr:
            ptr = self._ptr
            super(loop, self).destroy()

            assert self._ptr is None
            libuv.uv_stop(ptr)
            closed_failed = libuv.uv_loop_close(ptr)
            if closed_failed:
                assert closed_failed == libuv.UV_EBUSY
                # Walk the open handlers, close them, then
                # run the loop once to clear them out and
                # close again.

                def walk(handle, _arg):
                    if not libuv.uv_is_closing(handle):
                        libuv.uv_close(handle, ffi.NULL)

                libuv.uv_walk(ptr,
                              ffi.callback("void(*)(uv_handle_t*,void*)",
                                           walk),
                              ffi.NULL)

                ran_has_more_callbacks = libuv.uv_run(ptr, libuv.UV_RUN_ONCE)
                if ran_has_more_callbacks:
                    libuv.uv_run(ptr, libuv.UV_RUN_NOWAIT)
                closed_failed = libuv.uv_loop_close(ptr)
                assert closed_failed == 0, closed_failed

            # XXX: Do we need to uv_loop_delete the non-default loop?
            # Probably...

    def debug(self):
        """
        Return all the handles that are open and their ref status.
        """
        handle_state = namedtuple("HandleState",
                                  ['handle',
                                   'watcher',
                                   'ref',
                                   'active',
                                   'closing'])
        handles = []

        def walk(handle, _arg):
            data = handle.data
            if data:
                watcher = ffi.from_handle(data)
            else:
                watcher = None
            handles.append(handle_state(handle,
                                        watcher,
                                        libuv.uv_has_ref(handle),
                                        libuv.uv_is_active(handle),
                                        libuv.uv_is_closing(handle)))

        libuv.uv_walk(self._ptr,
                      ffi.callback("void(*)(uv_handle_t*,void*)",
                                   walk),
                      ffi.NULL)
        return handles

    def ref(self):
        pass

    def unref(self):
        # XXX: Called by _run_callbacks.
        pass

    def break_(self, how=None):
        libuv.uv_stop(self._ptr)

    def reinit(self):
        # TODO: How to implement? We probably have to simply
        # re-__init__ this whole class? Does it matter?
        # OR maybe we need to uv_walk() and close all the handles?

        # XXX: libuv <= 1.9 simply CANNOT handle a fork unless you immediately
        # exec() in the child. There are multiple calls to abort() that
        # will kill the child process:
        # - The OS X poll implementation (kqueue) aborts on an error return
        # value; since kqueue FDs can't be inherited, then the next call
        # to kqueue in the child will fail and get aborted; fork() is likely
        # to be called during the gevent loop, meaning we're deep inside the
        # runloop already, so we can't even close the loop that we're in:
        # it's too late, the next call to kqueue is already scheduled.
        # - The threadpool, should it be in use, also aborts
        # (https://github.com/joyent/libuv/pull/1136)
        # - There global shared state that breaks signal handling
        # and leads to an abort() in the child, EVEN IF the loop in the parent
        # had already been closed
        # (https://github.com/joyent/libuv/issues/1405)

        #raise NotImplementedError()
        pass


    def run(self, nowait=False, once=False):
        # we can only respect one flag or the other.
        # nowait takes precedence because it can't block
        mode = libuv.UV_RUN_DEFAULT
        if once:
            mode = libuv.UV_RUN_ONCE
        if nowait:
            mode = libuv.UV_RUN_NOWAIT

        # if mode == libuv.UV_RUN_DEFAULT:
        #     print("looping in python")
        #     ptr = self._ptr
        #     ran_error = 0
        #     while ran_error == 0:
        #         ran_error = libuv.uv_run(ptr, libuv.UV_RUN_ONCE)
        #     if ran_error != 0:
        #         print("Error running loop", libuv.uv_err_name(ran_error),
        #               libuv.uv_strerror(ran_error))
        #     return ran_error
        return libuv.uv_run(self._ptr, mode)

    def now(self):
        return libuv.uv_now(self._ptr)

    def update(self):
        libuv.uv_update_time(self._ptr)

    @property
    def default(self):
        return self._ptr == libuv.uv_default_loop()

    def fileno(self):
        if self._ptr:
            fd = libuv.uv_backend_fd(self._ptr)
            if fd >= 0:
                return fd

    _sigchld_watcher = None
    _sigchld_callback_ffi = None

    def install_sigchld(self):
        if not self.default:
            return

        if self._sigchld_watcher:
            return

        self._sigchld_watcher = ffi.new('uv_signal_t*')
        libuv.uv_signal_init(self._ptr, self._sigchld_watcher)
        self._sigchld_callback_ffi = ffi.callback('void(*)(void*, int)',
                                                  self.__sigchld_callback)
        libuv.uv_signal_start(self._sigchld_watcher,
                              self._sigchld_callback_ffi,
                              signal.SIGCHLD)

    def __sigchld_callback(self, _handler, _signum):
        while True:
            try:
                pid, status, _usage = os.wait3(os.WNOHANG)
            except OSError:
                # Python 3 raises ChildProcessError
                break

            if pid == 0:
                break
            children_watchers = self._child_watchers.get(pid, []) + self._child_watchers.get(0, [])
            for watcher in children_watchers:
                watcher._set_status(status)


    def io(self, fd, events, ref=True, priority=None):
        # We don't keep a hard ref to the root object;
        # the caller should keep the multiplexed watcher
        # alive as long as its in use.
        # XXX: Note there is a cycle from io_watcher._handle -> io_watcher
        # so these aren't collected as soon as you think/hope.
        io_watchers = self._io_watchers
        try:
            io_watcher = io_watchers[fd]
        except KeyError:
            io_watcher = self._watchers.io(self, fd, self._watchers.io.EVENT_MASK)
            io_watchers[fd] = io_watcher

        return io_watcher.multiplex(events)
