import sys
import heapq
import collections
from Queue import Full, Empty

from gevent.greenlet import Timeout, Waiter, get_hub, getcurrent, _NONE
from gevent import core


class Queue(object):
    """Create a queue object with a given maximum size.

    If maxsize is less than zero or None, the queue size is infinite.

    Queue(0) is a channel, that is, its put() method always blocks until the
    item is delivered. (This is unlike the standard Queue, where 0 means
    infinite size).
    """

    def __init__(self, maxsize=None):
        if maxsize < 0:
            self.maxsize = None
        else:
            self.maxsize = maxsize
        self.getters = set()
        self.putters = set()
        self._event_unlock = None
        self._init(maxsize)

    # QQQ make maxsize a property whose setter schedules unlock if necessary

    def _init(self, maxsize):
        self.queue = collections.deque()

    def _get(self):
        return self.queue.popleft()

    def _put(self, item):
        self.queue.append(item)

    def __repr__(self):
        return '<%s at %s %s>' % (type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return '<%s %s>' % (type(self).__name__, self._format())

    def _format(self):
        result = 'maxsize=%r' % (self.maxsize, )
        if getattr(self, 'queue', None):
            result += ' queue=%r' % self.queue
        if self.getters:
            result += ' getters[%s]' % len(self.getters)
        if self.putters:
            result += ' putters[%s]' % len(self.putters)
        if self._event_unlock is not None:
            result += ' unlocking'
        return result

    def qsize(self):
        """Return the size of the queue."""
        return len(self.queue)

    def empty(self):
        """Return True if the queue is empty, False otherwise.

        Queue is not empty if there are greenlets blocking on put()
        """
        return not self.qsize() and not self.putters

    def full(self):
        """Return True if the queue is full, False otherwise.

        Queue(None) is never full.
        """
        return self.qsize() + len(self.putters) - len(self.getters) >= self.maxsize

    def put(self, item, block=True, timeout=None):
        """Put an item into the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until a free slot is available. If 'timeout' is
        a positive number, it blocks at most 'timeout' seconds and raises
        the Full exception if no free slot was available within that time.
        Otherwise ('block' is false), put an item on the queue if a free slot
        is immediately available, else raise the Full exception ('timeout'
        is ignored in that case).
        """
        if self.maxsize is None or self.qsize() < self.maxsize:
            # there's a free slot, put an item right away
            self._put(item)
            if self.getters:
                self._schedule_unlock()
        elif not block and get_hub().greenlet is getcurrent():
            # we're in the mainloop, so we cannot wait; we can switch() to other greenlets though
            # find a getter and deliver an item to it
            while self.getters:
                getter = self.getters.pop()
                if getter:
                    self._put(item)
                    item = self._get()
                    getter.switch(item)
                    return
            raise Full
        elif block:
            waiter = ItemWaiter(item)
            self.putters.add(waiter)
            timeout = Timeout(timeout, Full)
            try:
                if self.getters:
                    self._schedule_unlock()
                result = waiter.wait()
                assert result is waiter, "Invalid switch into Queue.put: %r" % (result, )
                if waiter.item is not _NONE:
                    self._put(item)
            finally:
                timeout.cancel()
                self.putters.discard(waiter)
        else:
            raise Full

    def put_nowait(self, item):
        """Put an item into the queue without blocking.

        Only enqueue the item if a free slot is immediately available.
        Otherwise raise the Full exception.
        """
        self.put(item, False)

    def get(self, block=True, timeout=None):
        """Remove and return an item from the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until an item is available. If 'timeout' is
        a positive number, it blocks at most 'timeout' seconds and raises
        the Empty exception if no item was available within that time.
        Otherwise ('block' is false), return an item if one is immediately
        available, else raise the Empty exception ('timeout' is ignored
        in that case).
        """
        if self.qsize():
            if self.putters:
                self._schedule_unlock()
            return self._get()
        elif not block and get_hub().greenlet is getcurrent():
            # special case to make get_nowait() runnable in the mainloop greenlet
            # there are no items in the queue; try to fix the situation by unlocking putters
            while self.putters:
                putter = self.putters.pop()
                if putter:
                    # obtain the item directly from putter bypassing the queue
                    item = putter.item
                    putter.item = _NONE
                    putter.switch(putter)
                    return item
            raise Empty
        elif block:
            waiter = Waiter()
            timeout = Timeout(timeout, Empty)
            self.getters.add(waiter)
            try:
                if self.putters:
                    self._schedule_unlock()
                return waiter.wait()
            finally:
                self.getters.discard(waiter)
                timeout.cancel()
        else:
            raise Empty

    def get_nowait(self):
        """Remove and return an item from the queue without blocking.

        Only get an item if one is immediately available. Otherwise
        raise the Empty exception.
        """
        return self.get(False)

    def _unlock(self):
        try:
            while True:
                if self.qsize() and self.getters:
                    getter = self.getters.pop()
                    if getter:
                        try:
                            item = self._get()
                        except:
                            getter.throw(*sys.exc_info())
                        else:
                            getter.switch(item)
                elif self.putters and self.getters:
                    putter = self.putters.pop()
                    if putter:
                        getter = self.getters.pop()
                        if getter:
                            # deliver the item from putter to getter bypassing the queue
                            item = putter.item
                            putter.item = _NONE
                            getter.switch(item)
                            putter.switch(putter)
                        else:
                            self.putters.add(putter)
                elif self.putters and (self.getters or self.qsize() < self.maxsize):
                    putter = self.putters.pop()
                    putter.switch(putter)
                else:
                    break
        finally:
            self._event_unlock = None # QQQ maybe it's possible to obtain this info from libevent?
            # i.e. whether this event is pending _OR_ currently executing
        # testcase: 2 greenlets: while True: q.put(q.get()) - nothing else has a change to execute
        # to avoid this, schedule unlock with timer(0, ...) once in a while

    def _schedule_unlock(self):
        if self._event_unlock is None:
            self._event_unlock = core.active_event(self._unlock)
            # QQQ re-active event instead of creating a new one each time


class ItemWaiter(Waiter):
    __slots__ = ['item']

    def __init__(self, item):
        Waiter.__init__(self)
        self.item = item


class PriorityQueue(Queue):
    '''Variant of Queue that retrieves open entries in priority order (lowest first).

    Entries are typically tuples of the form:  (priority number, data).
    '''

    def _init(self, maxsize):
        self.queue = []

    def _put(self, item, heappush=heapq.heappush):
        heappush(self.queue, item)

    def _get(self, heappop=heapq.heappop):
        return heappop(self.queue)


class LifoQueue(Queue):
    '''Variant of Queue that retrieves most recently added entries first.'''

    def _init(self, maxsize):
        self.queue = []

    def _put(self, item):
        self.queue.append(item)

    def _get(self):
        return self.queue.pop()

