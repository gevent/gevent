#
# event.pyx
#
# libevent Python bindings
#
# Copyright (c) 2004 Dug Song <dugsong@monkey.org>
# Copyright (c) 2003 Martin Murray <murrayma@citi.umich.edu>
# Copyright (c) 2009-2010 Denis Bilenko <denis.bilenko@gmail.com>
#

"""Wrappers around libevent API.

This module provides a mechanism to execute a function when a
specific event on a file handle, file descriptor, or signal occurs,
or after a given time has passed. It also provides wrappers around
structures and functions from libevent-dns and libevent-http.

This module does not work with the greenlets. A callback passed
to a method from this module will be executed in the event loop,
which is running in the :class:`Hub <gevent.hub.Hub>` greenlet.
Therefore it must not use any synchronous gevent API,
that is, the functions that switch to the Hub. It's OK to call asynchronous
stuff like :func:`gevent.spawn`, :meth:`Event.set <gevent.event.Event.set` or
:meth:`Queue.put_nowait <gevent.queue.Queue.put_nowait>`.

The code is based on pyevent_.

.. _pyevent: http://code.google.com/p/pyevent/
"""

__author__ = ( 'Dug Song <dugsong@monkey.org>',
               'Martin Murray <mmurray@monkey.org>' )
__copyright__ = ( 'Copyright (c) 2004 Dug Song',
                  'Copyright (c) 2003 Martin Murray' )
__license__ = 'BSD'
__url__ = 'http://monkey.org/~dugsong/pyevent/'
__version__ = '0.4+'

__all__ = ['event', 'read_event', 'write_event', 'timer', 'signal', 'active_event',
           'init', 'dispatch', 'loop', 'get_version', 'get_method', 'get_header_version']
# note, that .pxi files append stuff to __all__

import sys
import traceback
from pprint import pformat

DEF EVENT_INTERNAL_AVAILABLE = False

cdef extern from "libevent-internal.h":
    pass


cdef extern from "sys/types.h":
    ctypedef unsigned char u_char

cdef extern from "Python.h":
    void   Py_INCREF(object o)
    void   Py_DECREF(object o)
    object PyString_FromStringAndSize(char *v, int len)
    object PyString_FromString(char *v)
    int    PyObject_AsCharBuffer(object obj, char **buffer, int *buffer_len)

ctypedef void (*event_handler)(int fd, short evtype, void *arg)


cdef extern from "libevent.h":

    # event.h:
    struct timeval:
        unsigned int tv_sec
        unsigned int tv_usec

    struct event_t "event":
        int   ev_fd
        short ev_events
        int   ev_flags
        void *ev_arg

    void* event_init()
    int event_reinit(void *base)
    char* event_get_version()
    char* event_get_method()
    void event_set(event_t *ev, int fd, short event, event_handler handler, void *arg)
    void evtimer_set(event_t *ev, event_handler handler, void *arg)
    int  event_add(event_t *ev, timeval *tv)
    int  event_del(event_t *ev)
    int  event_dispatch() nogil
    int  event_loop(int loop) nogil
    int  event_pending(event_t *ev, short, timeval *tv)
    void event_active(event_t *ev, int res, short ncalls)

    int EVLOOP_ONCE
    int EVLOOP_NONBLOCK
    char* _EVENT_VERSION

cdef extern from "string.h":
    char* strerror(int errnum)

cdef extern from "errno.h":
    int errno

IF EVENT_INTERNAL_AVAILABLE:

    cdef extern from "libevent-internal.h":
        struct event_base:
            int event_count         # counts number of total events
            int event_count_active  # counts number of active events

    def _event_count():
        cdef event_base* c = current_base
        return c.event_count

    def _event_count_active():
        cdef event_base* c = current_base
        return c.event_count_active

ELSE:

    ctypedef void* event_base


cdef extern from "libevent.h":
    event_base* current_base


EV_TIMEOUT = 0x01
EV_READ    = 0x02
EV_WRITE   = 0x04
EV_SIGNAL  = 0x08
EV_PERSIST = 0x10

cdef void __event_handler(int fd, short evtype, void *arg) with gil:
    cdef event ev = <event>arg
    try:
        assert ev.fd == fd, (ev.fd, fd)
        ev._callback(ev, evtype)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for %s\n\n' % (ev, ))
        except:
            pass
    finally:
        if not event_pending(&ev.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            Py_DECREF(ev)


cdef class event:
    """Create a new event object with a user callback.

    - *evtype*   -- bitmask of EV_READ or EV_WRITE, or EV_SIGNAL
    - *handle*   -- a file handle, descriptor, or socket for EV_READ or EV_WRITE; a signal number for EV_SIGNAL
    - *callback* -- user callback with ``(event, evtype)`` prototype
    - *arg*      -- optional object, which will be made available as :attr:`arg` property.
    """
    cdef event_t ev
    cdef object _callback, _arg

    def __init__(self, short evtype, int handle, callback, arg=None):
        self._callback = callback
        self._arg = arg
        cdef void* c_self = <void*>self
        if evtype == 0 and not handle:
            evtimer_set(&self.ev, __event_handler, c_self)
        else:
            event_set(&self.ev, handle, evtype, __event_handler, c_self)

    property callback:
        """User callback that will be called once the event is signalled.

        The prototype: ``callback(event instance, evtype)``.
        """

        def __get__(self):
            return self._callback

        def __set__(self, new):
            self._callback = new

    property arg:
        """Optional object set and read only by the user."""

        def __get__(self):
            return self._arg

        def __set__(self, new):
            self._arg = new

    property pending:
        """Return True if the event is still scheduled to run."""

        def __get__(self):
            return event_pending(&self.ev, EV_TIMEOUT|EV_SIGNAL|EV_READ|EV_WRITE, NULL)

    property fd:

        def __get__(self):
            return self.ev.ev_fd

    property events:

        def __get__(self):
            return self.ev.ev_events

    property events_str:

        def __get__(self):
            result = []
            cdef short events = self.ev.ev_events
            cdef short c_event
            for (event, txt) in ((EV_TIMEOUT, 'TIMEOUT'), (EV_READ, 'READ'), (EV_WRITE, 'WRITE'),
                                 (EV_SIGNAL, 'SIGNAL'), (EV_PERSIST, 'PERSIST')):
                c_event = event
                if events & c_event:
                    result.append(txt)
                    c_event = c_event ^ 0xffffff
                    events = events & c_event
            if events:
                result.append(hex(events))
            return '|'.join(result)

    property flags:

        def __get__(self):
            return self.ev.ev_flags

    def add(self, timeout=-1):
        """Add event to be executed after an optional *timeout* - number of seconds
        after which the event will be executed."""
        cdef timeval tv
        cdef double c_timeout
        cdef int result
        if not event_pending(&self.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            Py_INCREF(self)
        if timeout >= 0.0:
            c_timeout = <double>timeout
            tv.tv_sec = <long>c_timeout
            tv.tv_usec = <unsigned int>((c_timeout - <double>tv.tv_sec) * 1000000.0)
            result = event_add(&self.ev, &tv)
        else:
            result = event_add(&self.ev, NULL)
        if result < 0:
            raise IOError(errno, strerror(errno))

    def cancel(self):
        """Remove event from the event queue."""
        cdef int result
        if event_pending(&self.ev, EV_TIMEOUT|EV_SIGNAL|EV_READ|EV_WRITE, NULL):
            result = event_del(&self.ev)
            if result < 0:
                return result
            Py_DECREF(self)
            return result

    def __repr__(self):
        if self.pending:
            pending = ' pending'
        else:
            pending = ''
        if self.events_str:
            events_str = ' %s' % self.events_str
        else:
            events_str = ''
        return '<%s at %s%s fd=%s%s flags=0x%x cb=%s arg=%s>' % \
               (type(self).__name__, hex(id(self)), pending, self.fd, events_str, self.flags, self._callback, self._arg)

    def __str__(self):
        if self.pending:
            pending = ' pending'
        else:
            pending = ''
        if self.events_str:
            events_str = ' %s' % self.events_str
        else:
            events_str = ''
        cb = str(self._callback).replace('\n', '\n' + ' ' * 8)
        arg = pformat(self._arg, indent=2).replace('\n', '\n' + ' ' * 8)
        return '%s%s fd=%s%s flags=0x%x\n  cb  = %s\n  arg = %s' % \
               (type(self).__name__, pending, self.fd, events_str, self.flags, cb, arg)

    def __enter__(self):
        return self

    def __exit__(self, *exit_args):
        self.cancel()


cdef class read_event(event):
    """Create a new scheduled event with evtype=EV_READ"""

    def __init__(self, int handle, callback, timeout=-1, arg=None):
        event.__init__(self, EV_READ, handle, callback, arg)
        self.add(timeout)


cdef class write_event(event):
    """Create a new scheduled event with evtype=EV_WRITE"""

    def __init__(self, int handle, callback, timeout=-1, arg=None):
        event.__init__(self, EV_WRITE, handle, callback, arg)
        self.add(timeout)


class readwrite_event(event):
    """Create a new scheduled event with evtype=EV_READ|EV_WRITE"""

    def __init__(self, int handle, callback, timeout=-1, arg=None):
        event.__init__(self, EV_READ|EV_WRITE, handle, callback, arg)
        self.add(timeout)


cdef void __simple_handler(int fd, short evtype, void *arg) with gil:
    cdef event ev = <event>arg
    try:
        args, kwargs = ev._arg
        ev._callback(*args, **kwargs)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for %s\n\n' % (ev, ))
        except:
            pass
    finally:
        if not event_pending(&ev.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            Py_DECREF(ev)


cdef class timer(event):
    """Create a new scheduled timer"""

    def __init__(self, float seconds, callback, *args, **kwargs):
        self._callback = callback
        self._arg = (args, kwargs)
        evtimer_set(&self.ev, __simple_handler, <void*>self)
        self.add(seconds)


cdef class signal(event):
    """Create a new persistent signal event"""

    def __init__(self, int signalnum, callback, *args, **kwargs):
        self._callback = callback
        self._arg = (args, kwargs)
        event_set(&self.ev, signalnum, EV_SIGNAL|EV_PERSIST, __simple_handler, <void*>self)
        self.add(-1)


cdef class active_event(event):
    """An event that is scheduled to run in the current loop iteration"""

    def __init__(self, callback, *args, **kwargs):
        self._callback = callback
        self._arg = (args, kwargs)
        evtimer_set(&self.ev, __simple_handler, <void*>self)
        Py_INCREF(self)
        event_active(&self.ev, EV_TIMEOUT, 1)

    def add(self, timeout=-1):
        raise NotImplementedError


def init():
    """Initialize event queue."""
    event_init()


def dispatch():
    """Dispatch all events on the event queue.
    Returns 0 on success, and 1 if no events are registered.
    May raise IOError.
    """
    cdef int ret
    with nogil:
        ret = event_dispatch()
    if ret < 0:
        raise IOError(errno, strerror(errno))
    return ret


def loop(nonblock=False):
    """Dispatch all pending events on queue in a single pass.
    Returns 0 on success, and 1 if no events are registered.
    May raise IOError.
    """
    cdef int flags, ret
    flags = EVLOOP_ONCE
    if nonblock:
        flags = EVLOOP_ONCE|EVLOOP_NONBLOCK
    with nogil:
        ret = event_loop(flags)
    if ret < 0:
        raise IOError(errno, strerror(errno))
    return ret


def get_version():
    """Wrapper for :meth:`event_get_version`"""
    return event_get_version()


def get_method():
    """Wrapper for :meth:`event_get_method`"""
    return event_get_method()


cdef extern from *:
    cdef void emit_ifdef "#if defined(_EVENT_VERSION) //" ()
    cdef void emit_else  "#else //" ()
    cdef void emit_endif "#endif //" ()


# _EVENT_VERSION is available since libevent 1.4.0-beta

def get_header_version():
    """Return _EVENT_VERSION"""
    emit_ifdef()
    return _EVENT_VERSION
    emit_endif()

# event_reinit is available since libevent 1.4.1-beta,
# but I cannot check for existence of a function here, can I?
# so I'm going to use _EVENT_VERSION as an indicator of event_reinit presence
# which will work in every version other than 1.4.0-beta

def reinit():
    """Wrapper for :meth:`event_reinit`."""
    emit_ifdef()
    return event_reinit(current_base)
    emit_endif()

include "evdns.pxi"

# XXX - make sure event queue is always initialized.
init()

if get_version() != get_header_version() and get_header_version() is not None:
    import warnings
    msg = "libevent version mismatch: system version is %r but this gevent is compiled against %r" % (get_version(), get_header_version())
    warnings.warn(msg, UserWarning, stacklevel=2)

include "evbuffer.pxi"
include "evhttp.pxi"
