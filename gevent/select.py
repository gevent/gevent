# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.

from gevent.timeout import Timeout
from gevent.event import Event
from gevent.core import MAXPRI, READ, WRITE, EVENTS
from gevent.hub import get_hub

__implements__ = ['select']
__all__ = ['error'] + __implements__

__select__ = __import__('select')
error = __select__.error


def get_fileno(obj):
    try:
        fileno_f = obj.fileno
    except AttributeError:
        if not isinstance(obj, (int, long)):
            raise TypeError('argument must be an int, or have a fileno() method: %r' % (obj, ))
        return obj
    else:
        return fileno_f()


class SelectResult(object):

    __slots__ = ['read', 'write', 'event']

    def __init__(self):
        self.read = []
        self.write = []
        self.event = Event()

    def update(self, events, socket):
        if events & READ:
            self.read.append(socket)
            self.event.set()
        elif events & WRITE:
            self.write.append(socket)
            self.event.set()


def select(rlist, wlist, xlist, timeout=None):
    """An implementation of :meth:`select.select` that blocks only the current greenlet.

    Note: *xlist* is ignored.
    """
    watchers = []
    timeout = Timeout.start_new(timeout)
    io = get_hub().loop.io
    result = SelectResult()
    try:
        try:
            for readfd in rlist:
                watcher = io(get_fileno(readfd), 1)
                watcher.priority = MAXPRI
                watcher.start(result.update, EVENTS, readfd)
                watchers.append(watcher)
            for writefd in wlist:
                watcher = io(get_fileno(writefd), 2)
                watcher.priority = MAXPRI
                watcher.start(result.update, EVENTS, writefd)
                watchers.append(watcher)
        except IOError, ex:
            raise error(*ex.args)
        result.event.wait(timeout=timeout)
        return result.read, result.write, []
    finally:
        for watcher in watchers:
            watcher.stop()
        timeout.cancel()
