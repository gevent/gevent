import gevent
from gevent import core

def get_fileno(obj):
    try:
        f = obj.fileno
    except AttributeError:
        if not isinstance(obj, int):
            raise TypeError("Must be int of have file() method: %r" % (obj, ))
        return obj
    else:
        return f()


def select(read_list, write_list, error_list, t=None):
    hub = gevent.get_hub()
    t = None
    current = gevent.getcurrent()    
    assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
    allevents = []

    def callback(ev, fd, evtype):
        if evtype & core.EV_READ:
            current.switch(([ev.arg], [], []))
        elif evtype & core.EV_WRITE:
            current.switch(([], [ev.arg], []))
        else:
            current.switch(([], [], []))

    for r in read_list:
        allevents.append(core.read(get_fileno(r), callback, arg=r))
    for w in write_list:
        allevents.append(core.write(get_fileno(r), callback, arg=w))

    if t is not None:
        t = gevent.timeout(t)
    try:
        try:
            return hub.switch()
        except gevent.TimeoutError:
            return [], [], []
    finally:
        for evt in allevents:
            evt.cancel()
        if t is not None:
            t.cancel()

