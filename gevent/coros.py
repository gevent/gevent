# @author Donovan Preston
#
# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2008-2009, AG Projects
# Copyright (c) 2009, Denis Bilenko
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

import collections
import time
import traceback

from gevent.core import active_event
from gevent.hub import get_hub, getcurrent, sleep, spawn_raw


class Cancelled(RuntimeError):
    pass


class NOT_USED:
    def __repr__(self):
        return 'NOT_USED'

NOT_USED = NOT_USED()

class event(object):
    """An abstraction where an arbitrary number of coroutines
    can wait for one event from another.

    Events differ from channels in two ways:
      1) calling send() does not unschedule the current coroutine
      2) send() can only be called once; use reset() to prepare the event for
         another send()
    They are ideal for communicating return values between coroutines.

    >>> evt = event()
    >>> def baz(b):
    ...     evt.send(b + 1)
    ...
    >>> _ = spawn_raw(baz, 3)
    >>> evt.wait()
    4
    """
    _result = None
    def __init__(self):
        import warnings
        warnings.warn("coros.event is deprecated", DeprecationWarning, stacklevel=2)
        self._waiters = set()
        self.reset()

    def __str__(self):
        params = (self.__class__.__name__, hex(id(self)), self._result, self._exc, len(self._waiters))
        return '<%s at %s result=%r _exc=%r _waiters[%d]>' % params

    def reset(self):
        """ Reset this event so it can be used to send again.
        Can only be called after send has been called.

        >>> from gevent import coros
        >>> evt = coros.event()
        >>> evt.send(1)
        >>> evt.reset()
        >>> evt.send(2)
        >>> evt.wait()
        2

        Calling reset multiple times in a row is an error.

        >>> evt.reset()
        >>> evt.reset()
        Traceback (most recent call last):
        ...
        AssertionError: Trying to re-reset() a fresh event.

        """
        assert self._result is not NOT_USED, 'Trying to re-reset() a fresh event.'
        self.epoch = time.time()
        self._result = NOT_USED
        self._exc = None

    def ready(self):
        """ Return true if the wait() call will return immediately.
        Used to avoid waiting for things that might take a while to time out.
        For example, you can put a bunch of events into a list, and then visit
        them all repeatedly, calling ready() until one returns True, and then
        you can wait() on that one."""
        return self._result is not NOT_USED

    def has_exception(self):
        return self._exc is not None

    def has_result(self):
        return self._result is not NOT_USED and self._exc is None

    def poll(self, notready=None):
        if self.ready():
            return self.wait()
        return notready

    # QQQ make it return tuple (type, value, tb) instead of raising
    # because
    # 1) "poll" does not imply raising
    # 2) it's better not to screw up caller's sys.exc_info() by default
    #    (e.g. if caller wants to calls the function in except or finally)
    def poll_exception(self, notready=None):
        if self.has_exception():
            return self.wait()
        return notready

    def poll_result(self, notready=None):
        if self.has_result():
            return self.wait()
        return notready

    def wait(self):
        """Wait until another coroutine calls send.
        Returns the value the other coroutine passed to
        send.

        >>> evt = event()
        >>> def wait_on():
        ...    retval = evt.wait()
        ...    print "waited for", retval
        >>> _ = spawn_raw(wait_on)
        >>> evt.send('result')
        >>> sleep(0)
        waited for result

        Returns immediately if the event has already
        occured.

        >>> evt.wait()
        'result'
        """
        if self._result is NOT_USED:
            self._waiters.add(getcurrent())
            try:
                return get_hub().switch()
            finally:
                self._waiters.discard(getcurrent())
        if self._exc is not None:
            getcurrent().throw(*self._exc)
        return self._result

    def send(self, result=None, exc=None):
        """Makes arrangements for the waiters to be woken with the
        result and then returns immediately to the parent.

        >>> evt = event()
        >>> def waiter():
        ...     print 'about to wait'
        ...     result = evt.wait()
        ...     print 'waited for', result
        >>> _ = spawn_raw(waiter)
        >>> sleep(0)
        about to wait
        >>> evt.send('a')
        >>> sleep(0)
        waited for a

        It is an error to call send() multiple times on the same event.

        >>> evt.send('whoops')
        Traceback (most recent call last):
        ...
        AssertionError: Trying to re-send() an already-triggered event.

        Use reset() between send()s to reuse an event object.
        """
        assert self._result is NOT_USED, 'Trying to re-send() an already-triggered event.'
        self._result = result
        if exc is not None and not isinstance(exc, tuple):
            exc = (exc, )
        self._exc = exc
        if self._waiters:
            active_event(self._do_send, self._result, self._exc, self._waiters.copy())

    def _do_send(self, result, exc, waiters):
        while waiters:
            waiter = waiters.pop()
            if waiter in self._waiters:
                if exc is None:
                    waiter.switch(result)
                else:
                    waiter.throw(*exc)

    def send_exception(self, *args):
        # the arguments and the same as for greenlet.throw
        return self.send(None, args)


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
        if self._waiters:
            active_event(self._do_acquire)
        return True

    def _do_acquire(self):
        if self._waiters and self.counter>0:
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


def execute(func, *args, **kw):
    """ Executes an operation asynchronously in a new coroutine, returning
    an event to retrieve the return value.

    This has the same the CoroutinePool.execute method; the only
    difference is that this one creates a new coroutine instead of drawing
    from a pool.

    >>> from gevent import coros
    >>> evt = coros.execute(lambda a: ('foo', a), 1)
    >>> evt.wait()
    ('foo', 1)
    """
    evt = event()
    def _really_execute():
        evt.send(func(*args, **kw))
    spawn_raw(_really_execute)
    return evt


class Queue(object):

    def __init__(self):
        import warnings
        warnings.warn("coros.Queue is deprecated", DeprecationWarning, stacklevel=2)
        self.items = collections.deque()
        self._waiters = set()
        self._timer = None

    def __nonzero__(self):
        return len(self.items)>0

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)), len(self.items), len(self._waiters))
        return '<%s at %s items[%d] _waiters[%s]>' % params

    def send(self, result=None, exc=None):
        if exc is not None and not isinstance(exc, tuple):
            exc = (exc, )
        self.items.append((result, exc))
        if self._waiters and self._timer is None:
            self._timer = active_event(self._do_send)

    def send_exception(self, *args):
        # the arguments are the same as for greenlet.throw
        return self.send(exc=args)

    def _do_send(self):
        try:
            while self._waiters and self.items:
                waiter = self._waiters.pop()
                result, exc = self.items.popleft()
                waiter.switch((result, exc))
        finally:
            self._timer = None

    def wait(self):
        if self.items:
            result, exc = self.items.popleft()
            if exc is None:
                return result
            else:
                getcurrent().throw(*exc)
        else:
            self._waiters.add(getcurrent())
            try:
                result, exc = get_hub().switch()
                if exc is None:
                    return result
                else:
                    getcurrent().throw(*exc)
            finally:
                self._waiters.discard(getcurrent())

    def ready(self):
        return len(self.items) > 0

    def full(self):
        # for consistency with Channel
        return False

    def waiting(self):
        return len(self._waiters)


class Channel(object):

    def __init__(self, max_size=0):
        import warnings
        warnings.warn("coros.Channel is deprecated", DeprecationWarning, stacklevel=2)
        self.max_size = max_size
        self.items = collections.deque()
        self._waiters = set()
        self._senders = set()
        self._timer = None

    def __nonzero__(self):
        return len(self.items)>0

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        params = (self.__class__.__name__, hex(id(self)), self.max_size, len(self.items), len(self._waiters), len(self._senders))
        return '<%s at %s max=%s items[%d] _w[%s] _s[%s]>' % params

    def send(self, result=None, exc=None):
        if exc is not None and not isinstance(exc, tuple):
            exc = (exc, )
        if getcurrent() is get_hub():
            self.items.append((result, exc))
            if self._waiters and self._timer is None:
                self._timer = active_event(self._do_switch)
        else:
            if self._waiters and self._senders:
                sleep(0)
            self.items.append((result, exc))
            # note that send() does not work well with timeouts. if your timeout fires
            # after this point, the item will remain in the queue
            if self._waiters and self._timer is None:
                self._timer = active_event(self._do_switch)
            if len(self.items) > self.max_size:
                self._senders.add(getcurrent())
                try:
                    get_hub().switch()
                finally:
                    self._senders.discard(getcurrent())

    def send_exception(self, *args):
        # the arguments are the same as for greenlet.throw
        return self.send(exc=args)

    def _do_switch(self):
        try:
            while True:
                if self._waiters and self.items:
                    waiter = self._waiters.pop()
                    result, exc = self.items.popleft()
                    try:
                        waiter.switch((result, exc))
                    except:
                        traceback.print_exc()
                elif self._senders and len(self.items) <= self.max_size:
                    sender = self._senders.pop()
                    try:
                        sender.switch()
                    except:
                        traceback.print_exc()
                else:
                    break
        finally:
            self._timer = None

    def wait(self):
        if self.items:
            result, exc = self.items.popleft()
            if len(self.items) <= self.max_size and self._timer is None:
                self._timer = active_event(self._do_switch)
            if exc is None:
                return result
            else:
                getcurrent().throw(*exc)
        else:
            if self._senders and self._timer is None:
                self._timer = active_event(self._do_switch)
            self._waiters.add(getcurrent())
            try:
                result, exc = get_hub().switch()
                if exc is None:
                    return result
                else:
                    getcurrent().throw(*exc)
            finally:
                self._waiters.discard(getcurrent())

    def ready(self):
        return len(self.items) > 0

    def full(self):
        return len(self.items) >= self.max_size

    def waiting(self):
        return max(0, len(self._waiters) - len(self.items))

