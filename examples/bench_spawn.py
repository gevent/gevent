"""Benchmarking spawn() performance.
"""
import sys
from time import time

N = 20000
counter = 0


def incr(**kwargs):
    global counter
    counter += 1

if not sys.argv[1:]:
    sys.exit('USAGE: python bench_spawn.py none|gevent|eventlet [eventlet_hub]')

print sys.argv[1]

kwargs = {}
if sys.argv[-1]=='kwargs':
    kwargs = {'foo': 1, 'bar': 'hello'}
    del sys.argv[-1]

if sys.argv[1]=='none':
    start = time()
    for _ in xrange(N):
        incr(**kwargs)
    delta = time() - start
    assert counter == N, (counter, N)
    print '%.2f microseconds' % (delta*1000000.0/N)
elif sys.argv[1]=='gevent':
    import gevent
    print gevent.__file__
    from gevent import spawn, sleep
    start = time()
    for _ in xrange(N):
        spawn(incr, **kwargs)
    delta = time() - start
    print 'spawning: %d microseconds' % (delta*1000000.0/N)
    assert counter == 0, counter
    start = time()
    sleep(0)
    delta = time() - start
    assert counter == N, (counter, N)
    print 'switching: %d microseconds' % (delta*1000000.0/N)
elif sys.argv[1]=='eventlet':
    import eventlet
    print eventlet.__file__
    from eventlet.api import spawn, sleep, use_hub
    if sys.argv[2:]:
        use_hub(sys.argv[2])
    start = time()
    for _ in xrange(N):
        spawn(incr, **kwargs)
    delta = time() - start
    print 'spawning: %d microseconds' % (delta*1000000.0/N)
    assert counter == 0, counter
    start = time()
    sleep(0)
    delta = time() - start
    assert counter == N, (counter, N)
    print 'switching: %d microseconds' % (delta*1000000.0/N)
elif sys.argv[1]=='eventletproc':
    from eventlet.proc import spawn_greenlet as spawn
    from eventlet.api import sleep, use_hub
    if sys.argv[2:]:
        use_hub(sys.argv[2])
    start = time()
    for _ in xrange(N):
        spawn(incr, **kwargs)
    delta = time() - start
    print 'spawning: %d microseconds' % (delta*1000000.0/N)
    assert counter == 0, counter
    start = time()
    sleep(0)
    delta = time() - start
    assert counter == N, (counter, N)
    print 'switching: %d microseconds' % (delta*1000000.0/N)


