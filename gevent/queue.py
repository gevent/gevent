import sys
import heapq
import collections
from Queue import Full, Empty

from gevent.greenlet import Timeout, Waiter, get_hub, getcurrent
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

    def _remove(self, item):
        try:
            remove = self.queue.remove
        except AttributeError:
            deque_remove(self.queue, item)
        else:
            try:
                remove(item)
            except ValueError:
                pass

    def _peek(self):
        return self.queue[0]

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
        return not self.qsize()

    def full(self):
        """Return True if the queue is full, False otherwise.

        Queue is not full if there are greenlets blocking on get()
        Queue(None) is never full.
        """
        return (self.qsize()-len(self.getters)) >= self.maxsize

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
            self._put(item)
            if self.getters:
                self._schedule_unlock()
        elif self.getters and not block and get_hub().greenlet is getcurrent():
            # special case to make get_nowait() runnable in the mainloop greenlet
            putter = _ItemProxy(item, Waiter())
            self._put(putter)
            try:
                while self.getters:
                    getter = self.getters.pop()
                    if getter.waiting:
                        item = self._get()
                        if isinstance(item, _ItemProxy):
                            realitem, putter_waiter = item
                        else:
                            realitem = item
                        getter.switch(realitem)
                        if isinstance(item, _ItemProxy):
                            if putter_waiter.waiting:
                                # unlock the greenlet calling put()
                                putter_waiter.switch(putter_waiter)
                        return
                raise Full
            except:
                self._remove(putter)
                raise
        elif block:
            waiter = Waiter()
            putter = _ItemProxy(item, waiter)
            self.putters.add(waiter)
            timeout = Timeout(timeout, Full)
            try:
                self._put(putter)
                try:
                    if self.getters:
                        self._schedule_unlock()
                    result = waiter.wait()
                    assert result is waiter, "Invalid switch into Queue.put: %r" % (result, )
                except:
                    self._remove(putter)
                    raise
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
        if self.qsize() and not isinstance(self._peek(), _ItemProxy):
            if self.putters:
                self._schedule_unlock()
            return self._get()
        elif self.qsize() and not block and get_hub().greenlet is getcurrent():
            # special case to make get_nowait() runnable in the mainloop greenlet
            item = self._get()
            realitem, putter_waiter = item
            putter_waiter.switch(putter_waiter)
            return realitem
        elif block or self.qsize():
            if not block:
                timeout = 0
            waiter = Waiter()
            timeout = Timeout(timeout, Empty)
            try:
                self.getters.add(waiter)
                try:
                    if self.qsize():
                        self._schedule_unlock()
                    return waiter.wait()
                except:
                    self.getters.discard(waiter)
                    raise
            finally:
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
                    if getter.waiting:
                        try:
                            item = self._get()
                        except:
                            getter.throw(*sys.exc_info())
                        else:
                            if isinstance(item, _ItemProxy):
                                realitem, putter_waiter = item
                            else:
                                realitem = item
                            getter.switch(realitem)
                            if isinstance(item, _ItemProxy):
                                if putter_waiter.waiting:
                                    # unlock the greenlet calling put()
                                    putter_waiter.switch(putter_waiter)
                elif self.putters and self.qsize()-len(self.putters) < self.maxsize:
                    putter = self.putters.pop()
                    if putter.waiting:
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


def deque_remove(deque, item):
    for index, x in enumerate(deque):
        if x==item:
            del deque[index]
            return


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


class _ItemProxy(object):

    def __init__(self, item, waiter):
        self._item = item
        self._waiter = waiter

    def __cmp__(self, other):
        return cmp(self._item, other)

    def __nonzero__(self):
        return bool(self._item)

    def __getattr__(self, item):
        return getattr(self._item, item)

    def __hash__(self):
        return self._item.__hash__()

    def __repr__(self):
        return '_ItemProxy(%r, %r)' % (self._item, self._waiter)

    def __str__(self):
        return self._item.__str__()

    # XXX: other methods

    def __iter__(self):
        yield self._item
        yield self._waiter

