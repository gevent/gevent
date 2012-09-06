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
import weakref


cdef extern from "sys/types.h":
    ctypedef unsigned char u_char

cdef extern from "Python.h":
     struct PyObject:
       pass
     ctypedef PyObject* PyObjectPtr "PyObject*"
     void   Py_INCREF(PyObjectPtr o)
     void   Py_DECREF(PyObjectPtr o)
     void   Py_XDECREF(PyObjectPtr o)
     object PyString_FromStringAndSize(char *v, int len)
     object PyString_FromString(char *v)

cdef extern from "frameobject.h":
    ctypedef struct PyThreadState:
        PyObjectPtr exc_type
        PyObjectPtr exc_value
        PyObjectPtr exc_traceback

    PyThreadState* PyThreadState_GET()

ctypedef void (*event_handler)(int fd, short evtype, void *arg)

ctypedef void* event_base

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

    int EV_TIMEOUT
    int EV_READ
    int EV_WRITE
    int EV_SIGNAL
    int EV_PERSIST

    int EVLIST_TIMEOUT
    int EVLIST_INSERTED
    int EVLIST_SIGNAL
    int EVLIST_ACTIVE
    int EVLIST_INTERNAL
    int EVLIST_INIT


cdef extern from "string.h":
    char* strerror(int errnum)

cdef extern from "errno.h":
    int errno


cdef extern from "libevent.h":
    event_base* current_base


cdef void __event_handler(int fd, short evtype, void *arg) with gil:
    cdef event self = <event>arg
    try:
        self.callback(self, evtype)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for %s\n\n' % (self, ))
        except:
            traceback.print_exc()
        sys.exc_clear()
    finally:
        if not event_pending(&self.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            self._delref()


cdef class event:
    """Create a new event object with a user callback.

    - *evtype*   -- bitmask of EV_READ or EV_WRITE, or EV_SIGNAL
    - *handle*   -- a file handle, descriptor, or socket for EV_READ or EV_WRITE; a signal number for EV_SIGNAL
    - *callback* -- user callback with ``(event, evtype)`` prototype
    - *arg*      -- optional object, which will be made available as :attr:`arg` property.
    """
    cdef event_t ev
    cdef public object callback
    cdef public object arg
    cdef int _incref  # 1 if we already INCREFed this object once (because libevent references it)

    def __init__(self, short evtype, int handle, callback, arg=None):
        self.callback = callback
        self.arg = arg
        self._incref = 0
        cdef void* c_self = <void*>self
        if evtype == 0 and not handle:
            evtimer_set(&self.ev, __event_handler, c_self)
        else:
            event_set(&self.ev, handle, evtype, __event_handler, c_self)

    cdef _addref(self):
        if self._incref <= 0:
            Py_INCREF(<PyObjectPtr>self)
            self._incref += 1

    cdef _delref(self):
        if self._incref > 0:
            Py_DECREF(<PyObjectPtr>self)
            self._incref -= 1

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
            cdef int events = self.ev.ev_events
            cdef int c_event
            for (event, txt) in ((EV_TIMEOUT, 'TIMEOUT'), (EV_READ, 'READ'), (EV_WRITE, 'WRITE'),
                                 (EV_SIGNAL, 'SIGNAL'), (EV_PERSIST, 'PERSIST')):
                c_event = event
                if events & c_event:
                    result.append(txt)
                    events = events & (~c_event)
            if events:
                result.append(hex(events))
            return '|'.join(result)

    property flags:

        def __get__(self):
            return self.ev.ev_flags

    property flags_str:

        def __get__(self):
            result = []
            cdef int flags = self.ev.ev_flags
            cdef int c_flag
            for (flag, txt) in ((EVLIST_TIMEOUT, 'TIMEOUT'), (EVLIST_INSERTED, 'INSERTED'), (EVLIST_SIGNAL, 'SIGNAL'),
                                (EVLIST_ACTIVE, 'ACTIVE'), (EVLIST_INTERNAL, 'INTERNAL'), (EVLIST_INIT, 'INIT')):
                c_flag = flag
                if flags & c_flag:
                    result.append(txt)
                    flags = flags & (~c_flag)
            if flags:
                result.append(hex(flags))
            return '|'.join(result)

    def add(self, timeout=None):
        """Add event to be executed after an optional *timeout* - number of seconds
        after which the event will be executed."""
        cdef timeval tv
        cdef double c_timeout
        cdef int result
        if timeout is None:
            result = event_add(&self.ev, NULL)
        else:
            c_timeout = <double>timeout
            if c_timeout < 0.0:
                #raise ValueError('Expected a non-negative number or None: %r' % (timeout, ))
                import warnings
                warnings.warn('Negative timeouts are deprecated. Use None to disable timeout.', DeprecationWarning, stacklevel=2)
                result = event_add(&self.ev, NULL)
            else:
                tv.tv_sec = <long>c_timeout
                tv.tv_usec = <unsigned int>((c_timeout - <double>tv.tv_sec) * 1000000.0)
                result = event_add(&self.ev, &tv)
        if result < 0:
            if errno:
                raise IOError(errno, strerror(errno))
            else:
                raise IOError("event_add(fileno=%s) returned %s" % (self.fd, result))
        self._addref()

    def cancel(self):
        """Remove event from the event queue."""
        cdef int result
        if event_pending(&self.ev, EV_TIMEOUT|EV_SIGNAL|EV_READ|EV_WRITE, NULL):
            result = event_del(&self.ev)
            if result < 0:
                return result
            self._delref()
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
        return '<%s at %s%s fd=%s%s flags=%s cb=%s arg=%s>' % \
               (type(self).__name__, hex(id(self)), pending, self.fd, events_str, self.flags_str, self.callback, self.arg)

    def __str__(self):
        if self.pending:
            pending = ' pending'
        else:
            pending = ''
        if self.events_str:
            events_str = ' %s' % self.events_str
        else:
            events_str = ''
        cb = str(self.callback).replace('\n', '\n' + ' ' * 8)
        arg = pformat(self.arg, indent=2).replace('\n', '\n' + ' ' * 8)
        return '%s%s fd=%s%s flags=%s\n  cb  = %s\n  arg = %s' % \
               (type(self).__name__, pending, self.fd, events_str, self.flags_str, cb, arg)

    def __enter__(self):
        return self

    def __exit__(self, *exit_args):
        self.cancel()


cdef class read_event(event):
    """Create a new scheduled event with evtype=EV_READ"""

    def __init__(self, int handle, callback, timeout=None, arg=None, persist=False):
        cdef short evtype = EV_READ
        if persist:
            evtype = evtype | EV_PERSIST
        event.__init__(self, evtype, handle, callback, arg)
        self.add(timeout)


cdef class write_event(event):
    """Create a new scheduled event with evtype=EV_WRITE"""

    def __init__(self, int handle, callback, timeout=None, arg=None, persist=False):
        cdef short evtype = EV_WRITE
        if persist:
            evtype = evtype | EV_PERSIST
        event.__init__(self, evtype, handle, callback, arg)
        self.add(timeout)


class readwrite_event(event):
    """Create a new scheduled event with evtype=EV_READ|EV_WRITE"""

    def __init__(self, int handle, callback, timeout=None, arg=None, persist=False):
        cdef short evtype = EV_READ|EV_WRITE
        if persist:
            evtype = evtype | EV_PERSIST
        event.__init__(self, evtype, handle, callback, arg)
        self.add(timeout)


cdef void __simple_handler(int fd, short evtype, void *arg) with gil:
    cdef event self = <event>arg
    try:
        args, kwargs = self.arg
        self.callback(*args, **kwargs)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback for %s\n\n' % (self, ))
        except:
            traceback.print_exc()
        sys.exc_clear()
    finally:
        if not event_pending(&self.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            self._delref()


cdef class timer(event):
    """Create a new scheduled timer"""

    def __init__(self, float seconds, callback, *args, **kwargs):
        self.callback = callback
        self.arg = (args, kwargs)
        evtimer_set(&self.ev, __simple_handler, <void*>self)
        self.add(seconds)


cdef class signal(event):
    """Create a new persistent signal event"""

    def __init__(self, int signalnum, callback, *args, **kwargs):
        self.callback = callback
        self.arg = (args, kwargs)
        event_set(&self.ev, signalnum, EV_SIGNAL|EV_PERSIST, __simple_handler, <void*>self)
        self.add()


cdef class active_event(event):
    """An event that is scheduled to run in the current loop iteration"""

    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.arg = (args, kwargs)
        evtimer_set(&self.ev, __simple_handler, <void*>self)
        self._addref()
        event_active(&self.ev, EV_TIMEOUT, 1)

    def add(self, timeout=None):
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


# _EVENT_VERSION is available since libevent 1.4.0-beta

def get_header_version():
    """Return _EVENT_VERSION"""
    return _EVENT_VERSION

# event_reinit is available since libevent 1.4.1-beta,
# but I cannot check for existence of a function here, can I?
# so I'm going to use _EVENT_VERSION as an indicator of event_reinit presence
# which will work in every version other than 1.4.0-beta

def reinit():
    """Wrapper for :meth:`event_reinit`."""
    return event_reinit(current_base)

include "evdns.pxi"

# XXX - make sure event queue is always initialized.
init()

if get_version() != get_header_version() and get_header_version() is not None and get_version() != '1.3.99-trunk':
    import warnings
    msg = "libevent version mismatch: system version is %r but this gevent is compiled against %r" % (get_version(), get_header_version())
    warnings.warn(msg, UserWarning, stacklevel=2)

include "evbuffer.pxi"
include "evhttp.pxi"

def set_exc_info(object type, object value):
    cdef PyThreadState* tstate = PyThreadState_GET()
    Py_XDECREF(tstate.exc_type)
    Py_XDECREF(tstate.exc_value)
    Py_XDECREF(tstate.exc_traceback)
    if value is None:
        tstate.exc_type = NULL
        tstate.exc_value = NULL
    else:
        Py_INCREF(<PyObjectPtr>type)
        Py_INCREF(<PyObjectPtr>value)
        tstate.exc_type = <PyObjectPtr>type
        tstate.exc_value = <PyObjectPtr>value
    tstate.exc_traceback = NULL
