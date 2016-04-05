# If the logging module is imported *before* monkey patching,
# the existing handlers are correctly monkey patched to use gevent locks
import logging
logging.basicConfig()

import threading
import sys
PY2 = sys.version_info[0] == 2


def _inner_lock(lock):
    # The inner attribute changed between 2 and 3
    attr = getattr(lock, '_block' if not PY2 else '_RLock__block', None)
    return attr


def checkLocks(kind, ignore_none=True):
    handlers = logging._handlerList
    assert len(handlers) > 0

    for weakref in handlers:
        # In py26, these are actual handlers, not weakrefs
        handler = weakref() if callable(weakref) else weakref
        attr = _inner_lock(handler.lock)
        if attr is None and ignore_none:
            continue
        assert isinstance(attr, kind), (handler.lock, attr, kind)

    attr = _inner_lock(logging._lock)
    if attr is None and ignore_none:
        return
    assert isinstance(attr, kind)

checkLocks(type(threading._allocate_lock()))

import gevent.monkey
gevent.monkey.patch_all()

import gevent.lock

checkLocks(type(gevent.thread.allocate_lock()), ignore_none=False)
