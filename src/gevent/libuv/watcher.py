# pylint: disable=too-many-lines, protected-access, redefined-outer-name, not-callable
from __future__ import absolute_import, print_function

import functools
import weakref

import gevent.libuv._corecffi as _corecffi # pylint:disable=no-name-in-module,import-error

ffi = _corecffi.ffi # pylint:disable=no-member
libuv = _corecffi.lib # pylint:disable=no-member


from gevent._ffi import watcher as _base

_closing_handles = set()


@ffi.callback("void(*)(uv_handle_t*)")
def _uv_close_callback(handle):
    _closing_handles.remove(handle)

def _dbg(*args, **kwargs):
    # pylint:disable=unused-argument
    pass

#_dbg = print

_events = [(libuv.UV_READABLE, "READ"),
           (libuv.UV_WRITABLE, "WRITE")]

def _events_to_str(events): # export
    return _base.events_to_str(events, _events)

class UVFuncallError(ValueError):
    pass

class libuv_error_wrapper(object):
    # Makes sure that everything stored as a function
    # on the wrapper instances (classes, actually,
    # because this is used my the metaclass)
    # checks its return value and raises an error.
    # This expects that everything we call has an int
    # or void return value and follows the conventions
    # of error handling (that negative values are errors)
    def __init__(self, uv):
        self._libuv = uv

    def __getattr__(self, name):
        libuv_func = getattr(self._libuv, name)

        @functools.wraps(libuv_func)
        def wrap(*args, **kwargs):
            if len(args) > 0 and isinstance(args[0], watcher):
                args = args[1:]
            res = libuv_func(*args, **kwargs)
            if res is not None and res < 0:
                raise UVFuncallError(
                    str(ffi.string(libuv.uv_err_name(res)).decode('ascii')
                        + ' '
                        + ffi.string(libuv.uv_strerror(res)).decode('ascii')))
            return res

        setattr(self, name, wrap)

        return wrap


class ffi_unwrapper(object):
    # undoes the wrapping of libuv_error_wrapper for
    # the methods used by the metaclass that care

    def __init__(self, ff):
        self._ffi = ff

    def __getattr__(self, name):
        return getattr(self._ffi, name)

    def addressof(self, lib, name):
        assert isinstance(lib, libuv_error_wrapper)
        return self._ffi.addressof(libuv, name)


class watcher(_base.watcher):
    _FFI = ffi_unwrapper(ffi)
    _LIB = libuv_error_wrapper(libuv)

    _watcher_prefix = 'uv'
    _watcher_struct_pattern = '%s_t'
    _watcher_callback_name = '_gevent_generic_callback0'


    @classmethod
    def _watcher_ffi_close(cls, ffi_watcher):
        # Managing the lifetime of _watcher is tricky.
        # They have to be uv_close()'d, but that only
        # queues them to be closed in the *next* loop iteration.
        # The memory must stay valid for at least that long,
        # or assert errors are triggered. We can't use a ffi.gc()
        # pointer to queue the uv_close, because by the time the
        # destructor is called, there's no way to keep the memory alive
        # and it could be re-used.
        # So here we resort to resurrecting the pointer object out
        # of our scope, keeping it alive past this object's lifetime.
        # We then use the uv_close callback to handle removing that
        # reference. There's no context passed to the close callback,
        # so we have to do this globally.

        # Sadly, doing this causes crashes if there were multiple
        # watchers for a given FD, so we have to take special care
        # about that. See https://github.com/gevent/gevent/issues/790#issuecomment-208076604

        # Note that this cannot be a __del__ method, because we store
        # the CFFI handle to self on self, which is a cycle, and
        # objects with a __del__ method cannot be collected on CPython < 3.4

        # Instead, this is arranged as a callback to GC when the
        # watcher class dies. Obviously it's important to keep the ffi
        # watcher alive.

        if not libuv.uv_is_closing(ffi_watcher):
            #print("Closing handle", self._watcher)
            _closing_handles.add(ffi_watcher)
            libuv.uv_close(ffi_watcher, _uv_close_callback)

        ffi_watcher.data = ffi.NULL


    def _watcher_ffi_set_init_ref(self, ref):
        _dbg("Creating", type(self), "with ref", ref)
        self.ref = ref

    def _watcher_ffi_set_priority(self, priority):
        # libuv has no concept of priority
        pass

    def _watcher_ffi_init(self, args):
        # TODO: we could do a better job chokepointing this
        return self._watcher_init(self.loop.ptr,
                                  self._watcher,
                                  *args)

    def _watcher_ffi_start(self):
        _dbg("Starting", self)
        self._watcher_start(self._watcher, self._watcher_callback)
        _dbg("\tStarted", self)

    def _watcher_ffi_stop(self):
        _dbg("Stoping", self)
        self._watcher_stop(self._watcher)
        _dbg("Stoped", self)

    def _watcher_ffi_ref(self):
        _dbg("Reffing", self)
        libuv.uv_ref(self._watcher)

    def _watcher_ffi_unref(self):
        _dbg("Unreffing", self)
        libuv.uv_unref(self._watcher)

    def _watcher_ffi_start_unref(self):
        pass

    def _watcher_ffi_stop_ref(self):
        pass

    def _get_ref(self):
        # Convert 1/0 to True/False
        return True if libuv.uv_has_ref(self._watcher) else False

    def _set_ref(self, value):
        if value:
            self._watcher_ffi_ref()
        else:
            self._watcher_ffi_unref()

    ref = property(_get_ref, _set_ref)

    def feed(self, _revents, _callback, *_args):
        raise Exception("Not implemented")

class io(_base.IoMixin, watcher):
    _watcher_type = 'poll'
    _watcher_callback_name = '_gevent_poll_callback2'

    EVENT_MASK = libuv.UV_READABLE | libuv.UV_WRITABLE | libuv.UV_DISCONNECT

    _multiplex_watchers = None

    def __init__(self, loop, fd, events, ref=True, priority=None):
        super(io, self).__init__(loop, fd, events, ref=ref, priority=priority, _args=(fd,))
        self._fd = fd
        self._events = events

    def _get_fd(self):
        return self._fd

    @_base.not_while_active
    def _set_fd(self, fd):
        self._fd = fd
        self._watcher_ffi_init((fd,))

    def _get_events(self):
        return self._events

    @_base.not_while_active
    def _set_events(self, events):
        self._events = events

    def _watcher_ffi_start(self):
        self._watcher_start(self._watcher, self._events, self._watcher_callback)

    class _multiplexwatcher(object):

        def __init__(self, events, watcher):
            self.events = events
            self.callback = None
            self.args = ()
            self.pass_events = False
            self.ref = True

            # References:
            # These objects keep the original IO object alive;
            # the IO object SHOULD NOT keep these alive to avoid cycles
            # When they all go away, the original IO object can go
            # away. Hopefully that means that the FD they were opened for
            # has also gone away.
            self._watcher_ref = watcher

        def start(self, callback, *args, **kwargs):
            self.pass_events = kwargs.get("pass_events")
            self.callback = callback
            self.args = args

            watcher = self._watcher_ref
            if watcher is not None and not watcher.active:
                watcher._io_start()

        def stop(self):
            self.callback = None
            self.pass_events = None
            self.args = None
            watcher = self._watcher_ref
            watcher._io_maybe_stop()

        @property
        def active(self):
            return self.callback is not None

        @property
        def _watcher(self):
            # For testing.
            return self._watcher_ref._watcher


    def _io_maybe_stop(self):
        for r in self._multiplex_watchers:
            w = r()
            if w is None:
                continue
            if w.callback is not None:
                return
        # If we get here, nothing was started
        # so we can take ourself out of the polling set
        self.stop()

    def _io_start(self):
        self.start(self._io_callback, pass_events=True)

    def multiplex(self, events):
        if not self._multiplex_watchers:
            self._multiplex_watchers = []

        watcher = self._multiplexwatcher(events, self)
        watcher_ref = weakref.ref(watcher, self._multiplex_watchers.remove)
        # We must not keep a hard ref to the returned object.
        self._multiplex_watchers.append(watcher_ref)

        return watcher

    def _io_callback(self, events):
        if events < 0:
            # actually a status error code
            _dbg("Callback error on", self._fd,
                 ffi.string(libuv.uv_err_name(events)),
                 ffi.string(libuv.uv_strerror(events)))
            # XXX: We've seen one half of a FileObjectPosix pair
            # (the read side of a pipe) report errno 11 'bad file descriptor'
            # after the write side was closed and its watcher removed. But
            # we still need to attempt to read from it to clear out what's in
            # its buffers--if we return with the watcher inactive before proceeding to wake up
            # the reader, we get a LoopExit. So we can't return here and arguably shouldn't print it
            # either. The negative events mask will match the watcher's mask.
            # See test__fileobject.py:Test.test_newlines for an example.
            #return

        for watcher_ref in self._multiplex_watchers:
            watcher = watcher_ref()
            if not watcher or not watcher.callback:
                continue

            if events & watcher.events:
                if not watcher.pass_events:
                    watcher.callback(*watcher.args)
                else:
                    watcher.callback(events, *watcher.args)


class fork(_base.ForkMixin):
    # We'll have to implement this one completely manually
    # Right now it doesn't matter much since libuv doesn't survive
    # a fork anyway.

    def __init__(self, *args, **kwargs):
        pass

    def start(self, *args):
        pass

    def stop(self, *args):
        pass


class child(_base.ChildMixin, watcher):
    _watcher_skip_ffi = True
    # We'll have to implement this one completely manually.
    # Our approach is to use a SIGCHLD handler and the original
    # os.waitpid call.

    # On Unix, libuv's uv_process_t and uv_spawn use SIGCHLD,
    # just like libev does for its child watchers. So
    # we're not adding any new SIGCHLD related issues not already
    # present in libev.

    def __init__(self, loop, *args, **kwargs):
        self._async = loop.async()
        super(child, self).__init__(loop, *args, **kwargs)

    def _watcher_create(self, _args):
        return

    @property
    def _watcher_handle(self):
        return None

    def _watcher_ffi_init(self, args):
        return

    def _watcher_ffi_set_init_ref(self, ref):
        self._async.ref = ref

    def start(self, cb, *args):
        self.loop._child_watchers[self._pid].append(self)
        self.callback = cb
        self.args = args
        self._async.start(cb, *args)
        #watcher.start(self, cb, *args)

    @property
    def active(self):
        return self._async.active

    def stop(self):
        try:
            self.loop._child_watchers[self._pid].remove(self)
        except ValueError:
            pass
        self.callback = None
        self.args = None
        self._async.stop()

    def _set_status(self, status):
        self._rstatus = status
        self._async.send()


class async(_base.AsyncMixin, watcher):

    def _watcher_ffi_init(self, args):
        # It's dangerous to have a raw, non-initted struct
        # around; it will crash in uv_close() when we get GC'd,
        # and send() will also crash.
        # NOTE: uv_async_init is NOT idempotent. Calling it more than
        # once adds the uv_async_t to the internal queue multiple times,
        # and uv_close only cleans up one of them, meaning that we tend to
        # crash. Thus we have to be very careful not to allow that.
        return self._watcher_init(self.loop.ptr, self._watcher, ffi.NULL)

    def _watcher_ffi_start(self):
        # we're created in a started state, but we didn't provide a
        # callback (because if we did and we don't have a value in our
        # callback attribute, then python_callback would crash.) Note that
        # uv_async_t->async_cb is not technically documented as public.
        self._watcher.async_cb = self._watcher_callback

    def _watcher_ffi_stop(self):
        self._watcher.async_cb = ffi.NULL
        # We have to unref this because we're setting the cb behind libuv's
        # back, basically: once a async watcher is started, it can't ever be
        # stopped through libuv interfaces, so it would never lose its active
        # status, and thus if it stays reffed it would keep the event loop
        # from exiting.
        self._watcher_ffi_unref()

    def send(self):
        if libuv.uv_is_closing(self._watcher):
            raise Exception("Closing handle")
        libuv.uv_async_send(self._watcher)

    @property
    def pending(self):
        return None

class timer(_base.TimerMixin, watcher):

    def _update_now(self):
        self.loop.update()

    _again = False

    def _watcher_ffi_init(self, args):
        self._watcher_init(self.loop._ptr, self._watcher)
        self._after, self._repeat = args
        if self._after and self._after < 0.001:
            import warnings
            warnings.warn("libuv only supports millisecond timer resolution; "
                          "all times less will be set to 1 ms",
                          stacklevel=6)
            # The alternative is to effectively pass in int(0.1) == 0, which
            # means no sleep at all, which leads to excessive wakeups
            self._after = 0.001
        if self._repeat and self._repeat < 0.001:
            import warnings
            warnings.warn("libuv only supports millisecond timer resolution; "
                          "all times less will be set to 1 ms",
                          stacklevel=6)
            self._repeat = 0.001

    def _watcher_ffi_start(self):
        if self._again:
            libuv.uv_timer_again(self._watcher)
        else:
            try:
                self._watcher_start(self._watcher, self._watcher_callback,
                                    int(self._after * 1000),
                                    int(self._repeat * 1000))
            except ValueError:
                # in case of non-ints in _after/_repeat
                raise TypeError()

    def again(self, callback, *args, **kw):
        if not self.active:
            # If we've never been started, this is the same as starting us.
            # libuv makes the distinction, libev doesn't.
            self.start(callback, *args, **kw)
            return

        self._again = True
        try:
            self.start(callback, *args, **kw)
        finally:
            del self._again


class stat(_base.StatMixin, watcher):
    _watcher_type = 'fs_poll'
    _watcher_struct_name = 'gevent_fs_poll_t'
    _watcher_callback_name = '_gevent_fs_poll_callback3'

    def _watcher_create(self, ref):
        self._handle = type(self).new_handle(self)
        self._watcher = type(self).new(self._watcher_struct_pointer_type)
        self.loop._register_watcher(watcher, self._handle)
        self._watcher.handle.data = self._handle

    def _watcher_ffi_init(self, args):
        return self._watcher_init(self.loop._ptr, self._watcher)

    MIN_STAT_INTERVAL = 0.1074891 # match libev; 0.0 is default

    def _watcher_ffi_start(self):
        # libev changes this when the watcher is started
        if self._interval < self.MIN_STAT_INTERVAL:
            self._interval = self.MIN_STAT_INTERVAL
        self._watcher_start(self._watcher, self._watcher_callback,
                            self._cpath,
                            int(self._interval * 1000))

    @property
    def _watcher_handle(self):
        return self._watcher.handle.data

    @property
    def attr(self):
        if not self._watcher.curr.st_nlink:
            return
        return self._watcher.curr

    @property
    def prev(self):
        if not self._watcher.prev.st_nlink:
            return
        return self._watcher.prev


class signal(_base.SignalMixin, watcher):

    _watcher_callback_name = '_gevent_generic_callback1'

    def _watcher_ffi_init(self, args):
        self._watcher_init(self.loop._ptr, self._watcher)
        self.ref = False # libev doesn't ref these by default


    def _watcher_ffi_start(self):
        self._watcher_start(self._watcher, self._watcher_callback,
                            self._signalnum)


class idle(_base.IdleMixin, watcher):
    # Because libuv doesn't support priorities, idle watchers are
    # potentially quite a bit different than under libev
    pass
