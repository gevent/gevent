# test__import_wait.py calls this
import gevent


def fn2():
    return 2


def fn():
    return gevent.wait([gevent.spawn(fn2), gevent.spawn(fn2)])

x = gevent.spawn(fn).get()
