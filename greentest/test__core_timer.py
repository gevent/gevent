from gevent import core

called = []


def f():
    called.append(1)


def main():
    loop = core.loop(default=True)
    x = loop.timer(0.001)
    x.start(f)

    assert x.active, x.pending
    loop.run()
    assert x.pending == 0, x.pending
    assert called == [1], called
    assert x.callback is None, x.callback
    assert x.args is None, x.args
    x.stop()


if __name__ == '__main__':
    import sys
    gettotalrefcount = getattr(sys, 'gettotalrefcount', None)
    called[:] = []
    if gettotalrefcount is not None:
        print gettotalrefcount()
    main()
    called[:] = []
    if gettotalrefcount is not None:
        print gettotalrefcount()
