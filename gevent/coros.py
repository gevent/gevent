# Copyright (c) 2008-2009, AG Projects
# Copyright (c) 2009-2010, Denis Bilenko
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from gevent.core import active_event
from gevent.hub import get_hub, getcurrent


class Semaphore(object):
    """An unbounded semaphore.
    Optionally initialize with a resource count, then acquire() and release()
    resources as needed. Attempting to acquire() when count is zero suspends
    the calling coroutine until count becomes nonzero again.
    """

    def __init__(self, count=0):
        self.counter  = count
        self._waiters = set()

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)), self.counter, len(self._waiters))
        return '<%s at %s c=%s _w[%s]>' % params

    def __str__(self):
        params = (self.__class__.__name__, self.counter, len(self._waiters))
        return '<%s c=%s _w[%s]>' % params

    def locked(self):
        return self.counter <= 0

    def bounded(self):
        # for consistency with BoundedSemaphore
        return False

    def acquire(self, blocking=True):
        if not blocking and self.locked():
            return False
        if self.counter <= 0:
            self._waiters.add(getcurrent())
            try:
                while self.counter <= 0:
                    get_hub().switch()
            finally:
                self._waiters.discard(getcurrent())
        self.counter -= 1
        return True

    def __enter__(self):
        self.acquire()

    def release(self, blocking=True):
        # `blocking' parameter is for consistency with BoundedSemaphore and is ignored
        self.counter += 1
        if self._waiters and self.counter > 0:
            active_event(self._do_acquire)
        return True

    def _do_acquire(self):
        if self._waiters and self.counter > 0:
            waiter = self._waiters.pop()
            waiter.switch()

    def __exit__(self, typ, val, tb):
        self.release()

    @property
    def balance(self):
        # positive means there are free items
        # zero means there are no free items but nobody has requested one
        # negative means there are requests for items, but no items
        return self.counter - len(self._waiters)


class BoundedSemaphore(object):
    """A bounded semaphore.
    Optionally initialize with a resource count, then acquire() and release()
    resources as needed. Attempting to acquire() when count is zero suspends
    the calling coroutine until count becomes nonzero again.  Attempting to
    release() after count has reached limit suspends the calling coroutine until
    count becomes less than limit again.
    """
    def __init__(self, count, limit):
        if count > limit:
            # accidentally, this also catches the case when limit is None
            raise ValueError("'count' cannot be more than 'limit'")
        self.lower_bound = Semaphore(count)
        self.upper_bound = Semaphore(limit-count)

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)), self.balance, self.lower_bound, self.upper_bound)
        return '<%s at %s b=%s l=%s u=%s>' % params

    def __str__(self):
        params = (self.__class__.__name__, self.balance, self.lower_bound, self.upper_bound)
        return '<%s b=%s l=%s u=%s>' % params

    def locked(self):
        return self.lower_bound.locked()

    def bounded(self):
        return self.upper_bound.locked()

    def acquire(self, blocking=True):
        if not blocking and self.locked():
            return False
        self.upper_bound.release()
        try:
            return self.lower_bound.acquire()
        except:
            self.upper_bound.counter -= 1
            # using counter directly means that it can be less than zero.
            # however I certainly don't need to wait here and I don't seem to have
            # a need to care about such inconsistency
            raise

    def __enter__(self):
        self.acquire()

    def release(self, blocking=True):
        if not blocking and self.bounded():
            return False
        self.lower_bound.release()
        try:
            return self.upper_bound.acquire()
        except:
            self.lower_bound.counter -= 1
            raise

    def __exit__(self, typ, val, tb):
        self.release()

    @property
    def balance(self):
        return self.lower_bound.balance - self.upper_bound.balance



