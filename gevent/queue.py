from __future__ import with_statement
from Queue import Full, Empty
from gevent.greenlet import Timeout
from gevent import coros


class Queue(object):
    """Create a queue object with a given maximum size.

    If maxsize is less than zero or None, the queue size is infinite.
    NOTE: Queue(0) won't be infinite, like a standard Queue would be.
    """
    def __init__(self, maxsize=None):
        if maxsize <= 0:
            self.q = coros.Queue()
        else:
            self.q = coros.Channel(maxsize)

    def qsize(self):
        """Return the size of the queue."""
        return len(self.q)

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return not bool(self.q)

    def full(self):
        """Return True if the queue is full, False otherwise."""
        return self.q.full()

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
        if block:
            if timeout is None:
                self.q.send(item)
            else:
                if timeout < 0:
                    raise ValueError("'timeout' must be a positive number")
                with Timeout(timeout, Full):
                    # XXX even if timeout fires, item ends up in a queue anyway, because
                    # Channel.send is not transactional
                    return self.q.send(item)
        else:
            if self.q.full():
                raise Full
            else:
                self.q.send(item)

    def put_nowait(self, item):
        """Put an item into the queue without blocking.

        Only enqueue the item if a free slot is immediately available.
        Otherwise raise the Full exception.
        """
        self.q.put(False)

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
        if block:
            if timeout is None:
                return self.q.wait()
            elif timeout < 0:
                raise ValueError("'timeout' must be a positive number")
            else:
                with Timeout(timeout, Empty):
                    return self.q.wait()
        else:
            if not self.q:
                raise Empty
            else:
                return self.q.wait()

    def get_nowait(self):
        """Remove and return an item from the queue without blocking.

        Only get an item if one is immediately available. Otherwise
        raise the Empty exception.
        """
        return self.get(False)

