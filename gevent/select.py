# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

from gevent import core
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout

__all__ = ['select']

def get_fileno(obj):
    try:
        f = obj.fileno
    except AttributeError:
        if not isinstance(obj, int):
            raise TypeError("Must be int or have file() method: %r" % (obj, ))
        return obj
    else:
        return f()


def select(read_list, write_list, error_list, timeout=None):
    """An implementation of :meth:`select.select` that blocks only the current greenlet."""
    # QQQ error_list is ignored
    hub = get_hub()
    current = getcurrent()
    assert hub is not current, 'do not call blocking functions from the mainloop'
    allevents = []

    def callback(ev, evtype):
        if evtype & core.EV_READ:
            current.switch(([ev.arg], [], []))
        elif evtype & core.EV_WRITE:
            current.switch(([], [ev.arg], []))
        else:
            current.switch(([], [], []))

    for r in read_list:
        allevents.append(core.read_event(get_fileno(r), callback, arg=r))
    for w in write_list:
        allevents.append(core.write_event(get_fileno(w), callback, arg=w))

    timeout = Timeout.start_new(timeout)
    try:
        try:
            result = hub.switch()
        except Timeout, t:
            if t is not timeout:
                raise
            return [], [], []
        assert hasattr(result, '__len__') and len(result)==3, "Invalid switch into select: %r" % (result, )
        return result
    finally:
        for evt in allevents:
            evt.cancel()
        timeout.cancel()

