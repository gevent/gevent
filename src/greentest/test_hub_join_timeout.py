from contextlib import contextmanager
import gevent
from gevent.event import Event
from time import time
from _six import xrange


SMALL = 0.1
FUZZY = SMALL / 2

# setting up signal does not affect join()
gevent.signal(1, lambda: None)  # wouldn't work on windows

from greentest import EXPECT_POOR_TIMER_RESOLUTION

@contextmanager
def expected_time(expected, fuzzy=None):
    if fuzzy is None:
        if EXPECT_POOR_TIMER_RESOLUTION:
            # The noted timer jitter issues on appveyor/pypy3
            fuzzy = expected * 5.0
        else:
            fuzzy = expected / 2.0
    start = time()
    yield
    elapsed = time() - start
    assert expected - fuzzy <= elapsed <= expected + fuzzy, 'Expected: %r; elapsed: %r; fuzzy %r' % (expected, elapsed, fuzzy)


def no_time(fuzzy=(0.001 if not EXPECT_POOR_TIMER_RESOLUTION else 1.0)):
    return expected_time(0, fuzzy=fuzzy)


for _a in xrange(2):

    # exiting because the spawned greenlet finished execution (spawn (=callback) variant)
    for _ in xrange(2):
        x = gevent.spawn(lambda: 5)
        with no_time(SMALL):
            result = gevent.wait(timeout=10)
        assert result is True, repr(result)
        assert x.dead, x
        assert x.value == 5, x

    # exiting because the spawned greenlet finished execution (spawn_later (=timer) variant)
    for _ in xrange(2):
        x = gevent.spawn_later(SMALL, lambda: 5)
        with expected_time(SMALL):
            result = gevent.wait(timeout=10)
        assert result is True, repr(result)
        assert x.dead, x

    # exiting because of timeout (the spawned greenlet still runs)
    for _ in xrange(2):
        x = gevent.spawn_later(10, lambda: 5)
        with expected_time(SMALL):
            result = gevent.wait(timeout=SMALL)
        assert result is False, repr(result)
        assert not x.dead, (x, x._start_event)
        x.kill()
        with no_time():
            result = gevent.wait()
        assert result is True

    # exiting because of event (the spawned greenlet still runs)
    for _ in xrange(2):
        x = gevent.spawn_later(10, lambda: 5)
        event = Event()
        event_set = gevent.spawn_later(SMALL, event.set)
        with expected_time(SMALL):
            result = gevent.wait([event])
        assert result == [event], repr(result)
        assert not x.dead, x
        assert event_set.dead
        assert event.is_set()
        x.kill()
        with no_time():
            result = gevent.wait()
        assert result is True

    # checking "ref=False" argument
    for _ in xrange(2):
        gevent.get_hub().loop.timer(10, ref=False).start(lambda: None)
        with no_time():
            result = gevent.wait()
        assert result is True

    # checking "ref=False" attribute
    for _d in xrange(2):
        w = gevent.get_hub().loop.timer(10)
        w.start(lambda: None)
        w.ref = False
        with no_time():
            result = gevent.wait()
        assert result is True
