import gevent
from gevent.hub import get_hub

called = []


def f():
    called.append(1)


def main():
    loop = get_hub().loop
    x = loop.run_callback(f)

    assert x, x
    gevent.sleep(0)
    assert called == [1], called
    assert not x, (x, bool(x))

    x = loop.run_callback(f)
    assert x, x
    x.stop()
    assert not x, x
    gevent.sleep(0)
    assert called == [1], called
    assert not x, x


if __name__ == '__main__':
    called[:] = []
    main()
