"""Benchmarking spawn() performance.
"""
from __future__ import print_function, absolute_import, division
import sys
import os
import time

try:
    xrange
except NameError:
    xrange = range

if hasattr(time, "perf_counter"):
    curtime = time.perf_counter  # 3.3
elif sys.platform.startswith('win'):
    curtime = time.clock
else:
    curtime = time.time

N = 100000
counter = 0


def incr(sleep, **_kwargs):
    global counter
    counter += 1
    sleep(0)


def noop(_p):
    pass


def _report(name, delta):
    print('%8s: %3.2f microseconds per greenlet' % (name, delta * 1000000.0 / N))

def test(spawn, sleep, kwargs):
    start = curtime()
    for _ in xrange(N):
        spawn(incr, sleep, **kwargs)
    _report('spawning', curtime() - start)
    assert counter == 0, counter
    start = curtime()
    sleep(0)
    _report('sleep(0)', curtime() - start)
    assert counter == N, (counter, N)


def bench_none(options):
    kwargs = options.kwargs
    start = curtime()
    for _ in xrange(N):
        incr(noop, **kwargs)
    assert counter == N, (counter, N)
    _report('noop', curtime() - start)


def bench_gevent(options):
    import gevent
    print('using gevent from %s' % gevent.__file__)
    from gevent import spawn, sleep
    test(spawn, sleep, options.kwargs)


def bench_geventraw(options):
    import gevent
    print('using gevent from %s' % gevent.__file__)
    from gevent import sleep, spawn_raw
    test(spawn_raw, sleep, options.kwargs)


def bench_geventpool(options):
    import gevent
    print('using gevent from %s' % gevent.__file__)
    from gevent import sleep
    from gevent.pool import Pool
    p = Pool()
    test(p.spawn, sleep, options.kwargs)
    start = curtime()

    p.join()

    _report('joining', curtime() - start)



def bench_eventlet(options):
    try:
        import eventlet
    except ImportError:
        if options.ignore_import_errors:
            return
        raise
    print('using eventlet from %s' % eventlet.__file__)
    from eventlet import spawn, sleep
    from eventlet.hubs import use_hub
    if options.eventlet_hub is not None:
        use_hub(options.eventlet_hub)
    test(spawn, sleep, options.kwargs)



def bench_all():
    from time import sleep
    error = 0
    names = sorted(all())

    for func in names:
        cmd = '%s %s %s --ignore-import-errors' % (sys.executable, __file__, func)
        print(cmd)
        sys.stdout.flush()
        sleep(0.01)
        if os.system(cmd):
            error = 1
            print('%s failed' % cmd)
        print('')
    for func in names:
        cmd = '%s %s --with-kwargs %s --ignore-import-errors' % (sys.executable, __file__, func)
        print(cmd)
        sys.stdout.flush()
        if os.system(cmd):
            error = 1
            print('%s failed' % cmd)
        print('')
    if error:
        sys.exit(1)


def all():
    result = [x for x in globals() if x.startswith('bench_') and x != 'bench_all']
    try:
        result.sort(key=lambda x: globals()[x].func_code.co_firstlineno)
    except AttributeError:
        result.sort(key=lambda x: globals()[x].__code__.co_firstlineno)
    result = [x.replace('bench_', '') for x in result]
    return result


def all_functions():
    return [globals()['bench_%s' % x] for x in all()]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-kwargs', default=False, action='store_true')
    parser.add_argument('--eventlet-hub')
    parser.add_argument('--ignore-import-errors', action='store_true')
    parser.add_argument('benchmark', choices=all() + ['all'])
    options = parser.parse_args()
    if options.with_kwargs:
        options.kwargs = {'foo': 1, 'bar': 'hello'}
    else:
        options.kwargs = {}
    if options.benchmark == 'all':
        bench_all()
    else:
        function = globals()['bench_' + options.benchmark]
        function(options)

if __name__ == '__main__':
    main()
