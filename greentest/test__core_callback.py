import gevent
from gevent.hub import get_hub

called = []


def f():
    called.append(1)


def main():
    loop = get_hub().loop
    x = loop.callback()
    x.start(f)

    assert x.active, x.pending
    gevent.sleep(0)
    assert x.pending == 0, x.pending
    assert called == [1], called

    x = loop.callback()
    x.start(f)
    assert x.pending == 1, x.pending
    x.stop()
    assert x.pending == 0, x.pending
    gevent.sleep(0)
    assert called == [1], called
    assert x.pending == 0, x.pending
    gevent.sleep(0.1)


if __name__ == '__main__':
    called[:] = []
    main()
