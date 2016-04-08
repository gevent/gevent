"""
libuv loop implementation
"""

from __future__ import absolute_import, print_function

from gevent._ffi.loop import AbstractLoop
from gevent.libuv import _corecffi # pylint:disable=no-name-in-module,import-error
from gevent._ffi.loop import assign_standard_callbacks

ffi = _corecffi.ffi
libuv = _corecffi.lib

__all__ = [
]

_callbacks = assign_standard_callbacks(ffi, libuv)

from gevent.libuv import watcher as _watchers

class loop(AbstractLoop):

    error_handler = None

    _CHECK_POINTER = 'uv_check_t *'
    _CHECK_CALLBACK_SIG = "void(*)(void*)"

    _PREPARE_POINTER = 'uv_prepare_t *'
    _PREPARE_CALLBACK_SIG = "void(*)(void*)"

    _TIMER_POINTER = 'uv_timer_t *'

    def __init__(self, flags=None, default=None):
        AbstractLoop.__init__(self, ffi, libuv, _watchers, flags, default)


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

    def _init_and_start_check(self):
        libuv.uv_check_init(self._ptr, self._check)
        libuv.uv_check_start(self._check, self._check_callback_ffi)
        libuv.uv_unref(self._check)

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

    def destroy(self):
        if self._ptr:
            ptr = self._ptr
            super(loop, self).destroy()
            libuv.uv_loop_close(ptr)

    def ref(self):
        pass

    def unref(self):
        pass

    def break_(self, how=None):
        libuv.uv_stop(self._ptr)

    def reinit(self):
        # TODO: How to implement? We probably have to simply
        # re-__init__ this whole class? Does it matter?
        # OR maybe we need to uv_walk() and close all the handles?
        raise NotImplementedError()

    def run(self, nowait=False, once=False):
        # we can only respect one flag or the other.
        # nowait takes precedence because it can't block
        mode = libuv.UV_RUN_DEFAULT
        if once:
            mode = libuv.UV_RUN_ONCE
        if nowait:
            mode = libuv.UV_RUN_NOWAIT

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
            return libuv.uv_backend_fd(self._ptr)
