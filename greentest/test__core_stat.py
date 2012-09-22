from __future__ import with_statement
import gevent
import gevent.core
import os
import time


filename = 'tmp.test__core_stat.%s' % os.getpid()

hub = gevent.get_hub()

DELAY = 0.5

EV_USE_INOTIFY = getattr(gevent.core, 'EV_USE_INOTIFY', None)

try:
    open(filename, 'wb', buffering=0).close()
    assert os.path.exists(filename), filename

    def write():
        f = open(filename, 'wb', buffering=0)
        f.write('x')
        f.close()

    greenlet = gevent.spawn_later(DELAY, write)
    watcher = hub.loop.stat(filename)

    start = time.time()

    with gevent.Timeout(5 + DELAY + 0.5):
        hub.wait(watcher)

    reaction = time.time() - start - DELAY
    print 'Watcher %s reacted after %.4f seconds (write)' % (watcher, reaction)
    if reaction >= DELAY and EV_USE_INOTIFY:
        print 'WARNING: inotify failed (write)'
    assert reaction >= 0.0, 'Watcher %s reacted too early (write): %.3fs' % (watcher, reaction)
    assert watcher.attr is not None, watcher.attr
    assert watcher.prev is not None, watcher.prev

    greenlet.join()
    gevent.spawn_later(DELAY, os.unlink, filename)

    start = time.time()

    with gevent.Timeout(5 + DELAY + 0.5):
        hub.wait(watcher)

    reaction = time.time() - start - DELAY
    print 'Watcher %s reacted after %.4f seconds (unlink)' % (watcher, reaction)
    if reaction >= DELAY and EV_USE_INOTIFY:
        print 'WARNING: inotify failed (unlink)'
    assert reaction >= 0.0, 'Watcher %s reacted too early (unlink): %.3fs' % (watcher, reaction)
    assert watcher.attr is None, watcher.attr
    assert watcher.prev is not None, watcher.prev

finally:
    if os.path.exists(filename):
        os.unlink(filename)
