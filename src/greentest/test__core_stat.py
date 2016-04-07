from __future__ import print_function
import gevent
import gevent.core
import os
import sys
import time

#pylint: disable=protected-access

filename = 'tmp.test__core_stat.%s' % os.getpid()

hub = gevent.get_hub()

DELAY = 0.5

EV_USE_INOTIFY = getattr(gevent.core, 'EV_USE_INOTIFY', None)

WIN = sys.platform.startswith('win')

try:
    open(filename, 'wb', buffering=0).close()
    assert os.path.exists(filename), filename

    def write():
        with open(filename, 'wb', buffering=0) as f:
            f.write(b'x')

    start = time.time()
    greenlet = gevent.spawn_later(DELAY, write)
    # If we don't specify an interval, we default to zero.
    # libev interprets that as meaning to use its default interval,
    # which is about 5 seconds. If we go below it's minimum check
    # threshold, it bumps it up to the minimum.
    watcher = hub.loop.stat(filename, interval=-1)
    assert watcher.path == filename, (watcher.path, filename)
    filenames = filename if isinstance(filename, bytes) else filename.encode('ascii')
    assert watcher._paths == filenames, (watcher._paths, filenames)
    assert watcher.interval == -1

    def check_attr(name, none):
        # Deals with the complex behaviour of the 'attr' and 'prev'
        # attributes on Windows. This codifies it, rather than simply letting
        # the test fail, so we know exactly when and what changes it.
        try:
            x = getattr(watcher, name)
        except ImportError:
            if WIN:
                # the 'posix' module is not available
                pass
            else:
                raise
        else:
            if WIN:
                # The ImportError is only raised for the first time;
                # after that, the attribute starts returning None
                assert x is None, "Only None is supported on Windows"
            if none:
                assert x is None, x
            else:
                assert x is not None, x

    with gevent.Timeout(5 + DELAY + 0.5):
        hub.wait(watcher)

    reaction = time.time() - start - DELAY
    print('Watcher %s reacted after %.4f seconds (write)' % (watcher, reaction))
    if reaction >= DELAY and EV_USE_INOTIFY:
        print('WARNING: inotify failed (write)')
    assert reaction >= 0.0, 'Watcher %s reacted too early (write): %.3fs' % (watcher, reaction)
    check_attr('attr', False)
    check_attr('prev', False)
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
    check_attr('attr', True)
    check_attr('prev', False)

finally:
    if os.path.exists(filename):
        os.unlink(filename)
