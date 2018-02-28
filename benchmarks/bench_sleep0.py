"""
Benchmarking sleep(0) performance.
"""
from __future__ import print_function

import perf

try:
    xrange
except NameError:
    xrange = range



N = 100


def test(loops, sleep, arg):
    t0 = perf.perf_counter()
    for __ in range(loops):
        for _ in xrange(N):
            sleep(arg)
    return perf.perf_counter() - t0

def bench_gevent(loops, arg):
    from gevent import sleep
    from gevent import setswitchinterval
    setswitchinterval(1000)
    return test(loops, sleep, arg)

def bench_eventlet(loops, arg):
    from eventlet import sleep
    return test(loops, sleep, arg)


def main():
    runner = perf.Runner()
    for arg in (0, -1, 0.00001, 0.001):
        runner.bench_time_func('gevent sleep(%s)' % (arg,),
                               bench_gevent, arg,
                               inner_loops=N)
        runner.bench_time_func('eventlet sleep(%s)' % (arg,),
                               bench_eventlet, arg,
                               inner_loops=N)


if __name__ == '__main__':
    main()
