import gevent
from time import time


SMALL = 0.1
FUZZY = SMALL / 2


for _a in xrange(2):

    for _b in xrange(2):
        gevent.spawn_later(SMALL, lambda: 5)
        start = time()
        result = gevent.get_hub().join(timeout=10)
        assert result is True, repr(result)
        delay = time() - start
        assert SMALL - FUZZY <= delay <= SMALL + FUZZY, delay

    for _c in xrange(2):
        gevent.spawn_later(10, lambda: 5)
        start = time()
        result = gevent.get_hub().join(timeout=SMALL)
        assert result is None, repr(result)
        delay = time() - start
        assert SMALL - FUZZY <= delay <= SMALL + FUZZY, delay
