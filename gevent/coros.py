# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.

import sys
import traceback
from gevent.core import active_event
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout


class Semaphore(object):
    """An unbounded semaphore.
    Optionally initialize with a resource count, then acquire() and release()
    resources as needed. Attempting to acquire() when count is zero suspends
    the calling coroutine until count becomes nonzero again.
    """

    def __init__(self, count=0):
        self._links = []
        self.counter = count
        self._notifier = None

    def __str__(self):
        params = (self.__class__.__name__, self.counter, len(self._links))
        return '<%s counter=%s _links[%s]>' % params

    def locked(self):
        return self.counter <= 0

    def release(self):
        self.counter += 1
        if self._links and self.counter > 0 and self._notifier is None:
            self._notifier = active_event(self._notify_links, list(self._links))

    def _notify_links(self, links):
        try:
            for link in links:
                if self.counter <= 0:
                    return
                if link in self._links:
                    try:
                        link(self)
                    except:
                        traceback.print_exc()
                        try:
                            sys.stderr.write('Failed to notify link %r of %r\n\n' % (link, self))
                        except:
                            traceback.print_exc()
        finally:
            self._notifier = None

    def rawlink(self, callback):
        """Register a callback to call when a counter is more than zero.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.append(callback)
        if self.counter > 0 and self._notifier is None:
            self._notifier = active_event(self._notify_links, list(self._links))

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
        except ValueError:
            pass

    def wait(self, timeout=None):
        if self.counter > 0:
            return self.counter
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                timer = Timeout.start_new(timeout)
                try:
                    try:
                        result = get_hub().switch()
                        assert result is self, 'Invalid switch into Semaphore.wait(): %r' % (result, )
                    except Timeout, ex:
                        if ex is not timer:
                            raise
                finally:
                    timer.cancel()
            finally:
                self.unlink(switch)
        return self.counter

    def acquire(self, blocking=True, timeout=None):
        if self.counter > 0:
            self.counter -= 1
            return True
        elif not blocking:
            return False
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                timer = Timeout.start_new(timeout)
                try:
                    try:
                        result = get_hub().switch()
                        assert result is self, 'Invalid switch into Semaphore.acquire(): %r' % (result, )
                    except Timeout, ex:
                        if ex is not timer:
                            raise
                finally:
                    timer.cancel()
            finally:
                self.unlink(switch)
            self.counter -= 1
            assert self.counter >= 0
            return True

    def __enter__(self):
        self.acquire()

    def __exit__(self, typ, val, tb):
        self.release()

    @property # REMOVE IT
    def balance(self):
        # positive means there are free items
        # zero means there are no free items but nobody has requested one
        # negative means there are requests for items, but no items
        return self.counter - len(self._links)


class DummySemaphore(object):

    def __str__(self):
        return '<%s>' % self.__class__.__name__

    def locked(self):
        return False

    def release(self):
        pass

    def rawlink(self, callback):
        pass

    def unlink(self, callback):
        pass

    def wait(self, timeout=None):
        pass

    def acquire(self, blocking=True, timeout=None):
        pass

    def __enter__(self):
        self.acquire()

    def __exit__(self, typ, val, tb):
        self.release()


class RLock(object):

    def __init__(self):
        self._block = Semaphore(1)
        self._owner = None
        self._count = 0

    def __repr__(self):
        return "<%s(%s, %d)>" % (
                self.__class__.__name__,
                self._owner,
                self._count)

    def acquire(self, blocking=1):
        me = getcurrent()
        if self._owner is me:
            self._count = self._count + 1
            return 1
        rc = self._block.acquire(blocking)
        if rc:
            self._owner = me
            self._count = 1
        return rc

    def __enter__(self):
        return self.acquire()

    def release(self):
        if self._owner is not getcurrent():
            raise RuntimeError("cannot release un-aquired lock")
        self._count = count = self._count - 1
        if not count:
            self._owner = None
            self._block.release()

    def __exit__(self, t, v, tb):
        self.release()

    # Internal methods used by condition variables

    def _acquire_restore(self, count_owner):
        count, owner = count_owner
        self._block.acquire()
        self._count = count
        self._owner = owner

    def _release_save(self):
        count = self._count
        self._count = 0
        owner = self.__owner
        self._owner = None
        self._block.release()
        return (count, owner)

    def _is_owned(self):
        return self.owner is getcurrent()

