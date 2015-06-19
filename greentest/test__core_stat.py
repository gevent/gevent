from __future__ import print_function
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
        f.write(b'x')
        f.close()

    start = time.time()
    greenlet = gevent.spawn_later(DELAY, write)
    # If we don't specify an interval, we default to zero.
    # libev interprets that as meaning to use its default interval,
    # which is about 5 seconds. If we go below it's minimum check
    # threshold, it bumps it up to the minimum.
    watcher = hub.loop.stat(filename, interval=-1)
    if hasattr(watcher, 'path'):
        assert watcher.path == filename
    assert watcher.interval == -1

    with gevent.Timeout(5 + DELAY + 0.5):
        hub.wait(watcher)

    reaction = time.time() - start - DELAY
    print('Watcher %s reacted after %.4f seconds (write)' % (watcher, reaction))
    if reaction >= DELAY and EV_USE_INOTIFY:
        print('WARNING: inotify failed (write)')
    assert reaction >= 0.0, 'Watcher %s reacted too early (write): %.3fs' % (watcher, reaction)
    assert watcher.attr is not None, watcher.attr
    assert watcher.prev is not None, watcher.prev
    # The watcher interval changed after it started; -1 is illegal
    assert watcher.interval != -1

    greenlet.join()
    gevent.spawn_later(DELAY, os.unlink, filename)

    start = time.time()

    with gevent.Timeout(5 + DELAY + 0.5):
        hub.wait(watcher)

    reaction = time.time() - start - DELAY
    print('Watcher %s reacted after %.4f seconds (unlink)' % (watcher, reaction))
    if reaction >= DELAY and EV_USE_INOTIFY:
        print('WARNING: inotify failed (unlink)')
    assert reaction >= 0.0, 'Watcher %s reacted too early (unlink): %.3fs' % (watcher, reaction)
    assert watcher.attr is None, watcher.attr
    assert watcher.prev is not None, watcher.prev

finally:
    if os.path.exists(filename):
        os.unlink(filename)
