"""Benchmarking spawn() performance.
"""
import sys
from time import time

N = 20000
counter = 0


def incr(sleep, **kwargs):
    global counter
    counter += 1
    sleep(0)

if not sys.argv[1:]:
    sys.exit('USAGE: python bench_spawn.py none|gevent|geventraw|geventpool|eventlet [eventlet_hub]')

print sys.argv[1]

kwargs = {}
if sys.argv[-1]=='kwargs':
    kwargs = {'foo': 1, 'bar': 'hello'}
    del sys.argv[-1]

def noop(p):
    pass

def test(spawn, sleep):
    start = time()
    for _ in xrange(N):
        spawn(incr, sleep, **kwargs)
    delta = time() - start
    print 'spawning: %.1f microseconds per greenlet' % (delta*1000000.0/N)
    assert counter == 0, counter
    start = time()
    sleep(0)
    delta = time() - start
    assert counter == N, (counter, N)
    print 'sleep(0): %.1f microseconds per greenlet' % (delta*1000000.0/N)

if sys.argv[1]=='none':
    start = time()
    for _ in xrange(N):
        incr(noop, **kwargs)
    delta = time() - start
    assert counter == N, (counter, N)
    print '%.2f microseconds' % (delta*1000000.0/N)
elif sys.argv[1]=='gevent':
    import gevent
    print gevent.__file__
    from gevent import spawn, sleep
    test(spawn, sleep)
elif sys.argv[1]=='geventraw':
    import gevent
    print gevent.__file__
    from gevent import sleep
    from gevent.rawgreenlet import spawn
    test(spawn, sleep)
elif sys.argv[1]=='geventpool':
    import gevent
    print gevent.__file__
    from gevent import sleep
    from gevent.pool import Pool
    p = Pool()
    test(p.spawn, sleep)
    start = time()
    p.join()
    delta = time() - start
    print 'joining: %.1f microseconds per greenlet' % (delta*1000000.0/N)
elif sys.argv[1]=='eventlet':
    import eventlet
    print eventlet.__file__
    from eventlet.api import spawn, sleep, use_hub
    if sys.argv[2:]:
        use_hub(sys.argv[2])
    test(spawn, sleep)
elif sys.argv[1]=='eventlet1':
    from eventlet.proc import spawn_greenlet as spawn
    from eventlet.api import sleep, use_hub
    if sys.argv[2:]:
        use_hub(sys.argv[2])
    test(spawn, sleep, sleep)
