"""Benchmarking sleep(0) performance."""
import sys
from time import time


def noop(p):
    pass

N = 100000
ARG = 0


def test(sleep, arg):
    start = time()
    for _ in xrange(N):
        sleep(arg)
    return time() - start


def bench_none():
    test(noop)


def bench_gevent(arg=0):
    import gevent
    from gevent import sleep
    delta = test(sleep, arg)
    print ('gevent %s (%s): sleep(%r): %.1f microseconds' % (gevent.__version__, gevent.__file__, arg, delta * 1000000. / N))


def bench_eventlet(arg):
    try:
        import eventlet
    except ImportError, ex:
        sys.stderr.write('Failed to import eventlet: %s\n' % ex)
        return
    from eventlet.api import sleep
    delta = test(sleep, arg)
    print ('eventlet %s (%s): sleep(%r): %.1f microseconds' % (eventlet.__version__, eventlet.__file__, arg, delta * 1000000. / N))


def main():
    global N
    for arg in [0, -1, 0.00001]:
        bench_gevent(arg)
        bench_eventlet(arg)
    N = 1000
    bench_gevent(0.001)
    bench_eventlet(0.001)


if __name__ == '__main__':
    main()
