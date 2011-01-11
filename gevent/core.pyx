# Copyright (c) 2009-2010 Denis Bilenko and gevent contributors. See LICENSE for details.

"""Wrappers around libevent API.

This module provides a mechanism to execute a function when a
specific event on a file handle, file descriptor, or signal occurs,
or after a given time has passed. It also provides wrappers around
structures and functions from libevent-dns and libevent-http.

This module does not work with greenlets. A callback passed
to a method from this module will be executed in the event loop,
which is running in the :class:`Hub <gevent.hub.Hub>` greenlet.
Therefore it must not use any synchronous gevent API, that is, blocking
functions that need to switch to the Hub. It's OK to call asynchronous
stuff like :func:`gevent.spawn`, :meth:`Event.set <gevent.event.Event.set`
or :meth:`Queue.put_nowait <gevent.queue.Queue.put_nowait>`.

This module is very similar to pyevent_. In fact, it grew out of pyevent_ source code.
However it is currently more up to date with regard to libevent API.

.. _pyevent: http://code.google.com/p/pyevent/
"""

__all__ = ['event_base', 'evdns_base', 'event', 'get_version', 'get_header_version']
# note, that .pxi files append stuff to __all__

import sys
import traceback
from pprint import pformat
import weakref

cimport levent
EV_TIMEOUT = levent.EV_TIMEOUT
EV_READ = levent.EV_READ
EV_WRITE = levent.EV_WRITE
EV_SIGNAL = levent.EV_SIGNAL
EV_PERSIST = levent.EV_PERSIST

import _socket
gaierror = _socket.gaierror


cdef extern from "sys/types.h":
    ctypedef unsigned char u_char

cdef extern from "Python.h":
    void   Py_INCREF(object o)
    void   Py_DECREF(object o)
    object PyString_FromStringAndSize(char *v, int len)
    object PyString_FromString(char *v)
    void   PyOS_snprintf(void*, size_t, char*, ...)

cdef extern from "frameobject.h":
    ctypedef struct PyThreadState:
        void* exc_type
        void* exc_value
        void* exc_traceback
    PyThreadState* PyThreadState_GET()

cdef extern from "stdio.h":
    void* memset(void*, int, size_t)

cdef extern from "socketmodule.h":
    char* get_gaierror(int)
    object makesockaddr(int sockfd, void *, int addrlen, int proto)

ctypedef void (*event_handler)(int fd, short evtype, void *arg)
ctypedef void (*event_log_cb)(int severity, char *msg)

cdef extern from "string.h":
    char* strerror(int errnum)

cdef extern from "errno.h":
    int errno


cdef class event_base:

    cdef void* _ptr
    cdef public object _dns

    def __init__(self, size_t ptr=0):
        if ptr:
            self._ptr = <void*>ptr
        else:
            self._ptr = levent.event_base_new()
            if not self._ptr:
                if errno:
                    raise IOError(errno, strerror(errno))
                else:
                    raise IOError("event_base_new returned NULL")

    def __dealloc__(self):
        self.free()

    property ptr:

        def __get__(self):
            return <size_t>self._ptr

    property dns:

        def __get__(self):
            if self._dns is None:
                self._dns = evdns_base.new(self)
            return self._dns

    def dispatch(self):
        return levent.event_base_dispatch(self._ptr)

    def reinit(self):
        cdef int result = levent.event_reinit(self._ptr)
        if result != 0:
            raise IOError('event_reinit failed with %s' % result)

    def get_method(self):
        return levent.event_base_get_method(self._ptr)

    def get_info(self):
        return 'libevent-%s/%s' % (get_version(), self.get_method())

    def free(self):
        if self._ptr:
            levent.event_base_free(self._ptr)
            self._ptr = NULL
        if self._dns is not None:
            self._dns.free()
            self._dns = None

    def read_event(self, int handle, persist=False):
        cdef short evtype = levent.EV_READ
        if persist:
            evtype = evtype | levent.EV_PERSIST
        cdef event ev = event(evtype, handle, self)
        return ev

    def write_event(self, int handle, persist=False):
        cdef short evtype = levent.EV_WRITE
        if persist:
            evtype = evtype | levent.EV_PERSIST
        cdef event ev = event(evtype, handle, base=self)
        return ev

    def readwrite_event(self, int handle, persist=False):
        cdef short evtype = levent.EV_READ | levent.EV_WRITE
        if persist:
            evtype = evtype | levent.EV_PERSIST
        cdef event ev = event(evtype, handle, base=self)
        return ev

    def signal(self, int signalnum, callback, *args, **kwargs):
        cdef event ev = simple_event(levent.EV_SIGNAL|levent.EV_PERSIST, signalnum, base=self)
        ev.add(None, callback, *args, **kwargs)
        return ev

    def timer(self, seconds=None, callback=None, *args, **kwargs):
        cdef event ev = simple_event(0, -1, base=self)
        if callback is not None:
            ev.add(seconds, callback, *args, **kwargs)
        return ev

    def active_event(self, callback, *args, **kwargs):
        cdef event ev = simple_event(0, -1, base=self)
        ev.active(callback, *args, **kwargs)
        return ev


cdef class evdns_base:

    cdef void* _ptr
    cdef public event_base base

    def __init__(self, event_base base, size_t ptr=0):
        self.base = base
        self._ptr = <void*>ptr

    @classmethod
    def new(cls, object base, int init=1):
        cdef void* ptr = levent.evdns_base_new((<event_base?>base)._ptr, <int>init)
        if not ptr:
            if errno:
                raise IOError(errno, strerror(errno))
            else:
                raise IOError("evdns_base_new returned NULL")
        return cls(base, <size_t>ptr)

    property ptr:

        def __get__(self):
            return <size_t>self._ptr

    def free(self, int fail_requests=1):
        if self._ptr:
            self.base = None
            levent.evdns_base_free(self._ptr, fail_requests)
            self._ptr = NULL

    def add_nameserver(self, char* address):
        """Add a nameserver.

        This function parses a n IPv4 or IPv6 address from a string and adds it as a
        nameserver.  It supports the following formats:
        - [IPv6Address]:port
        - [IPv6Address]
        - IPv6Address
        - IPv4Address:port
        - IPv4Address

        If no port is specified, it defaults to 53."""
        cdef int result = levent.evdns_base_nameserver_ip_add(self._ptr, address)
        if result:
            if errno:
                raise IOError(errno, strerror(errno))
            else:
                raise IOError("evdns_base_nameserver_ip_add returned %r" % result)

    def count_nameservers(self):
        return levent.evdns_base_count_nameservers(self._ptr)

    def set_option(self, char* option, object val):
        """Set the value of a configuration option.

        The available configuration options are (as of libevent-2.0.8-rc):

        ndots, timeout, max-timeouts, max-inflight, attempts, randomize-case,
        bind-to, initial-probe-timeout, getaddrinfo-allow-skew."""
        # XXX auto add colon fix it: In versions before Libevent 2.0.3-alpha, the option name needed to end with a colon.
        cdef char* c_val
        if isinstance(val, str):
            c_val = val
        elif isinstance(val, (int, long, float)):
            val = str(val)
            c_val = val
        elif isinstance(val, unicode):
            val = val.encode('ascii')
            c_val = val
        else:
            raise TypeError('Expected a string or a number: %r' % (val, ))
        cdef int result = levent.evdns_base_set_option(self._ptr, option, c_val)
        if result:
            if errno:
                raise IOError(errno, strerror(errno))
            else:
                raise IOError("evdns_base_set_option returned %r" % result)

    def getaddrinfo(self, callback, host, port, int family=0, int socktype=0, int proto=0, int flags=0):
        # evdns and socket module do not match flags
        cdef char* nodename = NULL
        cdef char* servname = NULL
        cdef char pbuf[30]
        cdef levent.evutil_addrinfo hints
        if host is None:
            pass
        elif isinstance(host, unicode):
            host = host.encode('idna')
            nodename = host
        elif isinstance(host, str):
            nodename = host
        else:
            raise TypeError("getaddrinfo() first argument must be string or None")
        if port is None:
            pass
        elif isinstance(port, (int, long)):
            PyOS_snprintf(pbuf, sizeof(pbuf), "%ld", <long>port)
            servname = pbuf
        else:
            servname = <char*?>port  # check that it raises TypeError
        memset(&hints, 0, sizeof(hints))
        hints.ai_family = family
        hints.ai_socktype = socktype
        hints.ai_protocol = proto
        hints.ai_flags = flags
        cdef object param = [callback]
        Py_INCREF(param)
        cdef void* c_request = levent.evdns_getaddrinfo(self._ptr, nodename, servname, &hints, __getaddrinfo_handler, <void*>param)
        if c_request:
            request = getaddrinfo_request(<size_t>c_request)
            param.append(request)
            return request

    def resolve_ipv4(self, callback, char* host, int flags = 0):
        cdef object param = [callback]
        cdef void* c_request = levent.evdns_base_resolve_ipv4(self._ptr, host, flags, __evdns_handler, <void*>param)
        if c_request:
            request = evdns_request(<size_t>c_request)
            param.append(request)
            Py_INCREF(param)
            return request
        raise IOError('evdns_base_resolve_ipv4 returned NULL')


cdef void __getaddrinfo_handler(int code, levent.evutil_addrinfo* res, void* c_param) with gil:
    cdef object callback
    cdef object request
    cdef object param = <object>c_param
    Py_DECREF(param)
    cdef list result
    cdef char* canonname
    try:
        if len(param) == 1:
            callback = param[0]
            request = None
        else:
            callback, request = param

        if code == levent.EVUTIL_EAI_CANCEL:
            return

        if request is not None:
            if not request.ptr:
                return
            request.detach()

        if code:
            callback(None, gaierror(code, get_gaierror(code)))
        else:
            result = []
            while res:
                if res.ai_canonname:
                    canonname = res.ai_canonname
                else:
                    canonname = ''
                result.append((res.ai_family,
                               res.ai_socktype,
                               res.ai_protocol,
                               canonname,
                               makesockaddr(-1, res.ai_addr, res.ai_addrlen, res.ai_protocol)))
                res = res.ai_next
            callback(result, None)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback %r\n\n' % (callback, ))
        except:
            traceback.print_exc()
        sys.exc_clear()


cdef void __evdns_handler(int code, char typ, int count, int ttl, void *addrs, void *c_param) with gil:
    cdef object callback
    cdef object request
    cdef object param = <object>c_param
    Py_DECREF(param)
    cdef list result
    try:
        if len(param) == 1:
            callback = param[0]
            request = None
        else:
            callback, request = param

        if code == levent.DNS_ERR_CANCEL:
            return

        if request is not None:
            if not request.ptr:
                return
            request.detach()

        if type == levent.DNS_IPv4_A:
            result = []
            for i from 0 <= i < count:
                addr = PyString_FromStringAndSize(&(<char *>addrs)[i*4], 4)
                result.append(addr)
        elif type == levent.DNS_IPv6_AAAA:
            result = []
            for i from 0 <= i < count:
                addr = PyString_FromStringAndSize(&(<char *>addrs)[i*16], 16)
                result.append(addr)
        elif type == levent.DNS_PTR and count == 1:  # only 1 PTR possible
            result = PyString_FromString((<char **>addrs)[0])
        else:
            result = None
        if result is None:
            callback(None, gaierror(-1, 'XXX convert evdns code to gaierror code'))
        else:
            callback((result, ttl), None)
    except:
        traceback.print_exc()
        try:
            sys.stderr.write('Failed to execute callback %r\n\n' % (callback, ))
        except:
            traceback.print_exc()
        sys.exc_clear()


cdef class getaddrinfo_request:

    cdef void* _ptr

    def __init__(self, size_t ptr=0):
        self._ptr = <void*>ptr

    property ptr:

        def __get__(self):
            return <size_t>self._ptr

    def __repr__(self):
        return '%s(%x)' % (self.__class__.__name__, self.ptr)

    def detach(self):
        self._ptr = NULL

    def cancel(self):
        cdef void* ptr = self._ptr
        if ptr:
            self._ptr = NULL
            # actually cancelling request might crash (as of libevent-2.0.8-rc)
            #levent.evdns_getaddrinfo_cancel(ptr)


cdef class evdns_request:

    cdef void* _ptr

    def __init__(self, size_t ptr=0):
        self._ptr = <void*>ptr

    property ptr:

        def __get__(self):
            return <size_t>self._ptr

    def __repr__(self):
        return '%s(%x)' % (self.__class__.__name__, self.ptr)

    def detach(self):
        self._ptr = NULL

    def cancel(self):
        cdef void* ptr = self._ptr
        if ptr:
            self._ptr = NULL
            # actually cancelling request might crash (as of libevent-2.0.8-rc)
            #levent.evdns_cancel_request(NULL, ptr)


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
        if not levent.event_pending(&self.ev, levent.EV_READ|levent.EV_WRITE|levent.EV_SIGNAL|levent.EV_TIMEOUT, NULL):
            self._delref()


cdef class event:
    """Create a new event object with a user callback.

    - *evtype*   -- bitmask of EV_READ or EV_WRITE, or EV_SIGNAL
    - *handle*   -- a file handle, descriptor, or socket for EV_READ or EV_WRITE; a signal number for EV_SIGNAL
    - *callback* -- user callback with ``(event, evtype)`` prototype
    - *arg*      -- optional object, which will be made available as :attr:`arg` property.
    """
    cdef levent.event ev
    cdef public object callback
    cdef public object arg
    cdef int _incref  # 1 if we already INCREFed this object once (because libevent references it)

    def __init__(self, short evtype, int handle, event_base base=None):
        self._incref = 0
        cdef void* c_self = <void*>self
        levent.event_set(&self.ev, handle, evtype, __event_handler, c_self)
        if base is not None:
            levent.event_base_set((<event_base?>base)._ptr, &self.ev)

    cdef _addref(self):
        if self._incref <= 0:
            Py_INCREF(self)
            self._incref += 1

    cdef _delref(self):
        if self._incref > 0:
            Py_DECREF(self)
            self._incref -= 1
        self.callback = None
        self.arg = None

    property pending:
        """Return True if the event is still scheduled to run."""

        def __get__(self):
            return levent.event_pending(&self.ev, levent.EV_TIMEOUT|levent.EV_SIGNAL|levent.EV_READ|levent.EV_WRITE, NULL)

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
            for (event, txt) in ((levent.EV_TIMEOUT, 'TIMEOUT'),
                                 (levent.EV_READ, 'READ'),
                                 (levent.EV_WRITE, 'WRITE'),
                                 (levent.EV_SIGNAL, 'SIGNAL'),
                                 (levent.EV_PERSIST, 'PERSIST')):
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
            for (flag, txt) in ((levent.EVLIST_TIMEOUT, 'TIMEOUT'),
                                (levent.EVLIST_INSERTED, 'INSERTED'),
                                (levent.EVLIST_SIGNAL, 'SIGNAL'),
                                (levent.EVLIST_ACTIVE, 'ACTIVE'),
                                (levent.EVLIST_INTERNAL, 'INTERNAL'),
                                (levent.EVLIST_INIT, 'INIT')):
                c_flag = flag
                if flags & c_flag:
                    result.append(txt)
                    flags = flags & (~c_flag)
            if flags:
                result.append(hex(flags))
            return '|'.join(result)

    def add(self, timeout, callback, arg=None):
        cdef levent.timeval tv
        cdef double c_timeout
        cdef int result
        if not self.ev.ev_base:
            # libevent starting with 2.0.7 actually does check for this condition, so we should not
            raise AssertionError('ev_base is not set')
        if timeout is None:
            result = levent.event_add(&self.ev, NULL)
        else:
            c_timeout = <double>timeout
            if c_timeout < 0.0:
                raise ValueError('Invalid value for timeout, must be a non-negative number or None: %r' % (timeout, ))
            else:
                tv.tv_sec = <long>c_timeout
                tv.tv_usec = <unsigned int>((c_timeout - <double>tv.tv_sec) * 1000000.0)
                result = levent.event_add(&self.ev, &tv)
        if result < 0:
            if errno:
                raise IOError(errno, strerror(errno))
            else:
                raise IOError("event_add(fileno=%s) returned %s" % (self.fd, result))
        self.callback = callback
        self.arg = arg
        self._addref()

    def active(self, callback, arg):
        levent.event_active(&self.ev, levent.EV_TIMEOUT, 1)
        self.callback = callback
        self.arg = arg
        self._addref()

    def cancel(self):
        """Remove event from the event queue."""
        cdef int result
        # setting self.callback and self.arg to None to avoid refcounting cycles
        self.callback = None
        self.arg = None
        if levent.event_pending(&self.ev, levent.EV_TIMEOUT|levent.EV_SIGNAL|levent.EV_READ|levent.EV_WRITE, NULL):
            result = levent.event_del(&self.ev)
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
        if not levent.event_pending(&self.ev, levent.EV_READ|levent.EV_WRITE|levent.EV_SIGNAL|levent.EV_TIMEOUT, NULL):
            self._delref()


cdef class simple_event(event):

    def __init__(self, short evtype, int handle, base=None):
        self._incref = 0
        cdef void* c_self = <void*>self
        levent.event_set(&self.ev, handle, evtype, __simple_handler, c_self)
        if base is not None:
            levent.event_base_set((<event_base?>base)._ptr, &self.ev)

    def add(self, seconds, callback, *args, **kwargs):
        return event.add(self, seconds, callback, (args, kwargs))

    def active(self, callback, *args, **kwargs):
        return event.active(self, callback, (args, kwargs))


def get_version():
    """Wrapper for :meth:`event_get_version`"""
    return levent.event_get_version()


def get_header_version():
    """Return _EVENT_VERSION"""
    return levent._EVENT_VERSION


def set_exc_info(object value):
    cdef object typ
    cdef PyThreadState* tstate = PyThreadState_GET()
    if tstate.exc_type != NULL:
        Py_DECREF(<object>tstate.exc_type)
    if tstate.exc_value != NULL:
        Py_DECREF(<object>tstate.exc_value)
    if tstate.exc_traceback != NULL:
        Py_DECREF(<object>tstate.exc_traceback)
    if value is None:
        tstate.exc_type = NULL
        tstate.exc_value = NULL
    else:
        typ = type(value)
        Py_INCREF(typ)
        Py_INCREF(value)
        tstate.exc_type = <void*>typ
        tstate.exc_value = <void *>value
    tstate.exc_traceback = NULL


#include "evdns.pxi"
include "evbuffer.pxi"
include "evhttp.pxi"


if get_version() != get_header_version() and get_header_version() is not None and get_version() != '1.3.99-trunk':
    import warnings
    msg = "libevent version mismatch: system version is %r but this gevent is compiled against %r" % (get_version(), get_header_version())
    warnings.warn(msg, UserWarning, stacklevel=2)
