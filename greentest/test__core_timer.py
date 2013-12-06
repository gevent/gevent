from __future__ import print_function
from gevent import core

called = []


def f():
    called.append(1)


def main():
    loop = core.loop(default=True)
    x = loop.timer(0.001)
    x.start(f)

    assert x.active, x.pending
    try:
        x.priority = 1
        raise AssertionError('must not be able to change priority of active watcher')
    except AttributeError:
        pass
    loop.run()
    assert x.pending == 0, x.pending
    assert called == [1], called
    assert x.callback is None, x.callback
    assert x.args is None, x.args
    assert x.priority == 0, x
    x.priority = 1
    assert x.priority == 1, x
    x.stop()


if __name__ == '__main__':
    import sys
    gettotalrefcount = getattr(sys, 'gettotalrefcount', None)
    called[:] = []
    if gettotalrefcount is not None:
        print(gettotalrefcount())
    main()
    called[:] = []
    if gettotalrefcount is not None:
        print(gettotalrefcount())
