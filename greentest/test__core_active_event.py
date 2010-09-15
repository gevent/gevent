import gevent

called = []


def f():
    called.append(1)

x = gevent.core.active_event(f)
assert x.pending == 1, x.pending
gevent.sleep(0)
assert x.pending == 0, x.pending
assert called == [1], called

x = gevent.core.active_event(f)
assert x.pending == 1, x.pending
x.cancel()
assert x.pending == 0, x.pending
gevent.sleep(0)
assert called == [1], called
assert x.pending == 0, x.pending
