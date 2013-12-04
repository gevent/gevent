"""Benchmarking spawn() performance.
"""
from __future__ import print_function
import sys
import os
import random
from time import time
try:
    xrange
except NameError:
    xrange = range


N = 10000
counter = 0


def incr(sleep, **kwargs):
    global counter
    counter += 1
    sleep(0)


def noop(p):
    pass


def test(spawn, sleep, kwargs):
    start = time()
    for _ in xrange(N):
        spawn(incr, sleep, **kwargs)
    delta = time() - start
    print('spawning: %.1f microseconds per greenlet' % (delta * 1000000.0 / N))
    assert counter == 0, counter
    start = time()
    sleep(0)
    delta = time() - start
    assert counter == N, (counter, N)
    print('sleep(0): %.1f microseconds per greenlet' % (delta * 1000000.0 / N))


def bench_none(options):
    kwargs = options.kwargs
    start = time()
    for _ in xrange(N):
        incr(noop, **kwargs)
    delta = time() - start
    assert counter == N, (counter, N)
    print('%.2f microseconds' % (delta * 1000000.0 / N))


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
    start = time()
    p.join()
    delta = time() - start
    print('joining: %.1f microseconds per greenlet' % (delta * 1000000.0 / N))


def bench_eventlet(options):
    try:
        import eventlet
    except ImportError:
        if options.ignore_import_errors:
            return
        raise
    print('using eventlet from %s' % eventlet.__file__)
    from eventlet.api import spawn, sleep, use_hub
    if options.eventlet_hub is not None:
        use_hub(options.eventlet_hub)
    test(spawn, sleep, options.kwargs)


def bench_eventlet1(options):
    try:
        import eventlet
    except ImportError:
        if options.ignore_import_errors:
            return
        raise
    print('using eventlet from %s' % eventlet.__file__)
    from eventlet.proc import spawn_greenlet as spawn
    from eventlet.api import sleep, use_hub
    if options.eventlet_hub:
        use_hub(options.eventlet_hub)
    if options.with_kwargs:
        print('eventlet.proc.spawn_greenlet does support kwargs')
        return
    test(spawn, sleep, options.kwargs)


def bench_all(options):
    import time
    error = 0
    names = all()
    random.shuffle(names)
    for func in names:
        cmd = '%s %s %s --ignore-import-errors' % (sys.executable, __file__, func)
        print(cmd)
        sys.stdout.flush()
        time.sleep(0.01)
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


if __name__ == '__main__':
    USAGE = 'USAGE: python %s [--with-kwargs] [--eventlet-hub HUB] %s' % (sys.argv[0], '|'.join(all()))
    if not sys.argv[1:]:
        sys.exit(USAGE)
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--with-kwargs', default=False, action='store_true')
    parser.add_option('--eventlet-hub')
    parser.add_option('--ignore-import-errors', action='store_true')
    options, args = parser.parse_args()
    if options.with_kwargs:
        options.kwargs = {'foo': 1, 'bar': 'hello'}
    else:
        options.kwargs = {}
    if len(args) != 1:
        sys.exit(USAGE)
    if args[0] == 'all':
        bench_all(options)
    else:
        if args[0] not in all():
            sys.exit(USAGE)
        function = globals()['bench_' + args[0]]
        function(options)
