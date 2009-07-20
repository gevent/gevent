from gevent import core, greenlet

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
    hub = greenlet.get_hub()
    t = None
    current = greenlet.getcurrent()
    assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
    allevents = []

    def callback(ev, evtype):
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
        t = greenlet.Timeout(t)
    try:
        try:
            result = hub.switch()
        except greenlet.TimeoutError:
            return [], [], []
        assert hasattr(result, '__len__') and len(result)==3, "Invalid switch into select: %r" % (result, )
        return result
    finally:
        for evt in allevents:
            evt.cancel()
        if t is not None:
            t.cancel()

