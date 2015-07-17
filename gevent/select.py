# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
"""
Waiting for I/O completion.
"""
from __future__ import absolute_import
from gevent.event import Event
from gevent.hub import get_hub
from gevent.hub import integer_types


try:
    from select import poll as original_poll
    from select import POLLIN, POLLOUT
    __implements__ = ['select', 'poll']
except ImportError:
    original_poll = None
    __implements__ = ['select']

__all__ = ['error'] + __implements__

import select as __select__

error = __select__.error


def get_fileno(obj):
    try:
        fileno_f = obj.fileno
    except AttributeError:
        if not isinstance(obj, integer_types):
            raise TypeError('argument must be an int, or have a fileno() method: %r' % (obj,))
        return obj
    else:
        return fileno_f()


class SelectResult(object):
    __slots__ = ['read', 'write', 'event']

    def __init__(self):
        self.read = []
        self.write = []
        self.event = Event()

    def add_read(self, socket):
        self.read.append(socket)
        self.event.set()

    def add_write(self, socket):
        self.write.append(socket)
        self.event.set()


def select(rlist, wlist, xlist, timeout=None):
    """An implementation of :meth:`select.select` that blocks only the current greenlet.

    Note: *xlist* is ignored.
    """
    watchers = []
    loop = get_hub().loop
    io = loop.io
    MAXPRI = loop.MAXPRI
    result = SelectResult()
    try:
        try:
            for readfd in rlist:
                watcher = io(get_fileno(readfd), 1)
                watcher.priority = MAXPRI
                watcher.start(result.add_read, readfd)
                watchers.append(watcher)
            for writefd in wlist:
                watcher = io(get_fileno(writefd), 2)
                watcher.priority = MAXPRI
                watcher.start(result.add_write, writefd)
                watchers.append(watcher)
        except IOError as ex:
            raise error(*ex.args)
        result.event.wait(timeout=timeout)
        return result.read, result.write, []
    finally:
        for watcher in watchers:
            watcher.stop()

if original_poll is not None:
    class PollResult(object):
        __slots__ = ['events', 'event']

        def __init__(self):
            self.events = set()
            self.event = Event()

        def add_event(self, events, fd):
            result_flags = 0
            result_flags |= POLLIN if events & 1 else 0
            result_flags |= POLLOUT if events & 2 else 0
            self.events.add((fd, result_flags))
            self.event.set()

    class poll(object):
        def __init__(self):
            self.fds = {}
            self.loop = get_hub().loop

        def register(self, fd, eventmask=POLLIN | POLLOUT):
            flags = 0
            flags |= 1 if eventmask & POLLIN else 0
            flags |= 2 if eventmask & POLLOUT else 0
            watcher = self.loop.io(get_fileno(fd), flags)
            watcher.priority = self.loop.MAXPRI
            self.fds[fd] = watcher

        def modify(self, fd, eventmask):
            self.register(fd, eventmask)

        def poll(self, timeout=None):
            result = PollResult()
            try:
                for fd in self.fds:
                    self.fds[fd].start(result.add_event, get_fileno(fd), pass_events=True)
                if timeout is not None and -1 < timeout:
                    timeout /= 1000.0
                result.event.wait(timeout=timeout)
                return list(result.events)
            finally:
                for fd in self.fds:
                    self.fds[fd].stop()

        def unregister(self, fd):
            self.fds.pop(fd, None)
