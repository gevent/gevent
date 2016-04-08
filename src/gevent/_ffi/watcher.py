"""
Useful base classes for watchers. The available
watchers will depend on the specific event loop.
"""
# pylint:disable=not-callable
from __future__ import absolute_import, print_function
import sys
import os
import signal as signalmodule


from gevent._ffi.loop import GEVENT_CORE_EVENTS
from gevent._ffi.loop import _NOARGS

__all__ = [

]


class LazyOnClass(object):

    @classmethod
    def lazy(cls, cls_dict, func):
        cls_dict[func.__name__] = cls(func)

    def __init__(self, func, name=None):
        self.name = name or func.__name__
        self.func = func

    def __get__(self, inst, klass):
        if inst is None:
            return self

        val = self.func(inst)
        setattr(klass, self.name, val)
        return val


class AbstractWatcherType(type):
    """
    Base metaclass for watchers.

    To use, you will:

    - subclass the watcher class defined from this type.
    - optionally subclass this type
    """
    # pylint:disable=bad-mcs-classmethod-argument

    _FFI = None
    _LIB = None

    def __new__(cls, name, bases, cls_dict):
        if name != 'watcher':
            cls._fill_watcher(name, bases, cls_dict)
        return type.__new__(cls, name, bases, cls_dict)

    @classmethod
    def _fill_watcher(cls, name, bases, cls_dict):
        def _mro_get(attr, bases, error=True):
            for b in bases:
                try:
                    return getattr(b, attr)
                except AttributeError:
                    continue
            if error:
                raise AttributeError(attr)
        _watcher_prefix = cls_dict.get('_watcher_prefix') or _mro_get('_watcher_prefix', bases)

        if '_watcher_type' not in cls_dict:
            watcher_type = _watcher_prefix + '_' + name
            cls_dict['_watcher_type'] = watcher_type
        elif not cls_dict['_watcher_type'].startswith(_watcher_prefix):
            watcher_type = _watcher_prefix + '_' + cls_dict['_watcher_type']
            cls_dict['_watcher_type'] = watcher_type

        active_name = _watcher_prefix + '_is_active'

        def _watcher_is_active(self):
            return getattr(self._LIB, active_name)

        LazyOnClass.lazy(cls_dict, _watcher_is_active)

        watcher_struct_pattern = (cls_dict.get('_watcher_struct_pattern')
                                  or _mro_get('_watcher_struct_pattern', bases, False)
                                  or 'struct %s')
        watcher_struct_name = watcher_struct_pattern % (watcher_type,)

        def _watcher_struct_pointer_type(self):
            return self._FFI.typeof(watcher_struct_name + ' *')

        LazyOnClass.lazy(cls_dict, _watcher_struct_pointer_type)

        callback_name = (cls_dict.get('_watcher_callback_name')
                         or _mro_get('_watcher_callback_name', bases, False)
                         or '_gevent_generic_callback')

        def _watcher_callback(self):
            return self._FFI.addressof(self._LIB, callback_name)

        LazyOnClass.lazy(cls_dict, _watcher_callback)

        def _make_meth(name, watcher_name):
            def meth(self):
                lib_name = self._watcher_type + '_' + name
                return getattr(self._LIB, lib_name)
            meth.__name__ = watcher_name
            return meth

        for name in 'start', 'stop', 'init':
            watcher_name = '_watcher' + '_' + name
            if watcher_name not in cls_dict:
                LazyOnClass.lazy(cls_dict, _make_meth(name, watcher_name))

    def new_handle(cls, obj):
        return cls._FFI.new_handle(obj)

    def new(cls, kind):
        return cls._FFI.new(kind)

class watcher(object):

    _callback = None
    _args = None
    _handle = None # FFI object to self
    _watcher = None

    def __init__(self, _loop, ref=True, priority=None, args=_NOARGS):
        self.loop = _loop

        self._watcher_create(ref)

        if priority is not None:
            self._watcher_ffi_set_priority(priority)

        self._watcher_ffi_init(args)

    def _watcher_create(self, ref): # pylint:disable=unused-argument
        self._handle = type(self).new_handle(self)
        self._watcher = type(self).new(self._watcher_struct_pointer_type)
        # XXX: Must GC the _watche in libuv: uv_close()
        try:
            self._watcher.data = self._handle
        except AttributeError:
            import pdb; pdb.set_trace()

            raise

    def _watcher_ffi_set_priority(self, priority):
        pass

    def _watcher_ffi_init(self, args):
        raise NotImplementedError()

    def _watcher_ffi_start(self):
        raise NotImplementedError()

    def _watcher_ffi_stop(self):
        self._watcher_stop(self.loop._ptr, self._watcher)

    def _watcher_ffi_ref(self):
        raise NotImplementedError()

    def _watcher_ffi_unref(self):
        raise NotImplementedError()

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
    _watcher_is_active = None


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

    @property
    def ref(self):
        raise NotImplementedError()

    def _get_callback(self):
        return self._callback

    def _set_callback(self, cb):
        if not callable(cb) and cb is not None:
            raise TypeError("Expected callable, not %r" % (cb, ))
        if cb is None:
            if '_callback' in self.__dict__:
                del self._callback
        else:
            self._callback = cb
    callback = property(_get_callback, _set_callback)

    def _get_args(self):
        return self._args

    def _set_args(self, args):
        if not isinstance(args, tuple) and args is not None:
            raise TypeError("args must be a tuple or None")
        if args is None:
            if '_args' in self.__dict__:
                del self._args
        else:
            self._args = args

    args = property(_get_args, _set_args)

    def start(self, callback, *args):
        if callback is None:
            raise TypeError('callback must be callable, not None')
        self.callback = callback
        self.args = args or _NOARGS
        self._watcher_ffi_unref()
        self.loop._keepaliveset.add(self)
        self._watcher_ffi_start()

    def stop(self):
        self._watcher_ffi_ref()
        self._watcher_ffi_stop()
        self.loop._keepaliveset.discard(self)

        self.callback = None
        self.args = None

    def _get_priority(self):
        return None

    def _set_priority(self, priority):
        pass

    priority = property(_get_priority, _set_priority)


    @property
    def active(self):
        return True if self._watcher_is_active(self._watcher) else False

    @property
    def pending(self):
        return False

watcher = AbstractWatcherType('watcher', (object,), dict(watcher.__dict__))

import functools

def not_while_active(func):
    @functools.wraps(func)
    def nw(self, *args, **kwargs):
        if self.active:
            raise AttributeError("not while active")
        func(self, *args, **kwargs)
    return nw

class IoMixin(object):

    EVENT_MASK = 0

    def __init__(self, loop, fd, events, ref=True, priority=None, _args=None):
        # XXX: Win32: Need to vfd_open the fd and free the old one?
        # XXX: Win32: Need a destructor to free the old fd?
        if fd < 0:
            raise ValueError('fd must be non-negative: %r' % fd)
        if events & ~self.EVENT_MASK:
            raise ValueError('illegal event mask: %r' % events)
        super(IoMixin, self).__init__(loop, ref=ref, priority=priority,
                                      args=_args or (fd, events))

    def start(self, callback, *args, **kwargs):
        args = args or _NOARGS
        if kwargs.get('pass_events'):
            args = (GEVENT_CORE_EVENTS, ) + args
        super(IoMixin, self).start(callback, *args)


class TimerMixin(object):
    _watcher_type = 'timer'

    def __init__(self, loop, after=0.0, repeat=0.0, ref=True, priority=None):
        if repeat < 0.0:
            raise ValueError("repeat must be positive or zero: %r" % repeat)
        super(TimerMixin, self).__init__(loop, ref=ref, priority=priority, args=(after, repeat))

    def start(self, callback, *args, **kw):
        update = kw.get("update", True)
        if update:
            # Quoth the libev doc: "This is a costly operation and is
            # usually done automatically within ev_run(). This
            # function is rarely useful, but when some event callback
            # runs for a very long time without entering the event
            # loop, updating libev's idea of the current time is a
            # good idea."
            # So do we really need to default to true?
            self._update_now()
        super(TimerMixin, self).start(callback, *args)

    def _update_now(self):
        raise NotImplementedError()

    def again(self, callback, *args, **kw):
        raise NotImplementedError()


class SignalMixin(object):
    _watcher_type = 'signal'

    def __init__(self, loop, signalnum, ref=True, priority=None):
        if signalnum < 1 or signalnum >= signalmodule.NSIG:
            raise ValueError('illegal signal number: %r' % signalnum)
        # still possible to crash on one of libev's asserts:
        # 1) "libev: ev_signal_start called with illegal signal number"
        #    EV_NSIG might be different from signal.NSIG on some platforms
        # 2) "libev: a signal must not be attached to two different loops"
        #    we probably could check that in LIBEV_EMBED mode, but not in general
        super(SignalMixin, self).__init__(loop, ref=ref, priority=priority, args=(signalnum, ))


class IdleMixin(object):
    _watcher_type = 'idle'


class PrepareMixin(object):
    _watcher_type = 'prepare'


class CheckMixin(object):
    _watcher_type = 'check'


class ForkMixin(object):
    _watcher_type = 'fork'


class AsyncMixin(object):
    _watcher_type = 'async'

    def send(self):
        raise NotImplementedError()

    @property
    def pending(self):
        raise NotImplementedError()


class ChildMixin(object):

    def __init__(self, loop, pid, trace=0, ref=True):
        if not loop.default:
            raise TypeError('child watchers are only available on the default loop')
        loop.install_sigchld()
        self._pid = pid
        super(ChildMixin, self).__init__(loop, ref=ref, args=(pid, trace))

    def _format(self):
        return ' pid=%r rstatus=%r' % (self.pid, self.rstatus)

    @property
    def pid(self):
        return self._pid

    @property
    def rpid(self):
        return os.getpid()

    @property
    def rstatus(self):
        return 0

class StatMixin(object):

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
        self._cpath = self._FFI.new('char[]', self._paths)

        self._interval = interval
        super(StatMixin, self).__init__(_loop, ref=ref, priority=priority,
                                        args=(self._cpath,
                                              interval))

    @property
    def path(self):
        return self._path

    @property
    def attr(self):
        raise NotImplementedError

    @property
    def prev(self):
        raise NotImplementedError

    @property
    def interval(self):
        return self._interval
