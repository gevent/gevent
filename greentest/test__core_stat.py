import gevent
import gevent.core
import os
import time


filename = 'test__core_stat.%s' % os.getpid()

def unlink():
    try:
        os.unlink(filename)
    except OSError:
        pass

hub = gevent.get_hub()
watcher = hub.loop.stat(filename)

if getattr(gevent.core, 'EV_USE_INOTIFY', None):
    timeout = 0.3
else:
    timeout = 5.3

try:
    fobj = open(filename, 'wb', buffering=0)

    def write():
        fobj.write('x')
        fobj.close()

    gevent.spawn_later(0.2, write)

    start = time.time()

    with gevent.Timeout(timeout):
        hub.wait(watcher)

    print 'Watcher %r reacted after %.6f seconds' % (watcher, time.time() - start - 0.2)

    gevent.spawn_later(0.2, unlink)

    start = time.time()

    with gevent.Timeout(timeout):
        hub.wait(watcher)

    print 'Watcher %r reacted after %.2f seconds' % (watcher, time.time() - start - 0.2)

finally:
    unlink()
