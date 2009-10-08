# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

from collections import deque
from gevent.hub import GreenletExit, getcurrent
from gevent.greenlet import joinall, Greenlet
from gevent.timeout import Timeout

__all__ = ['GreenletSet', 'Pool']


class GreenletSet(object):
    """Maintain a set of greenlets that are still running.
    
    Links to each item and removes it upon notification.
    """
    greenlet_class = Greenlet

    def __init__(self, *args):
        assert len(args)<=1, args
        self.greenlets = set(*args)
        if args:
            for p in args[0]:
                p.rawlink(self.discard)
        # each item we kill we place in dying, to avoid killing the same greenlet twice
        self.dying = set()

    def __repr__(self):
        try:
            classname = self.__class__.__name__
        except AttributeError:
            classname = 'GreenletSet' # XXX check if 2.4 really uses this line
        return '<%s at %s %s>' % (classname, hex(id(self)), self.greenlets)

    def __len__(self):
        return len(self.greenlets)

    def __contains__(self, item):
        return item in self.greenlets

    def __iter__(self):
        return iter(self.greenlets)

    def add(self, p):
        p.rawlink(self.discard)
        self.greenlets.add(p)

    def discard(self, p):
        self.greenlets.discard(p)
        self.dying.discard(p)

    def spawn(self, func, *args, **kwargs):
        add = self.add
        p = self.greenlet_class.spawn(func, *args, **kwargs)
        add(p)
        return p

    def spawn_link(self, func, *args, **kwargs):
        p = self.spawn(func, *args, **kwargs)
        p.link()
        return p

    def spawn_link_value(self, func, *args, **kwargs):
        p = self.spawn(func, *args, **kwargs)
        p.link_value()
        return p

    def spawn_link_exception(self, func, *args, **kwargs):
        p = self.spawn(func, *args, **kwargs)
        p.link_exception()
        return p

#     def close(self):
#         """Prevents any more tasks from being submitted to the pool"""
#         self.add = RaiseException("This %s has been closed" % self.__class__.__name__)

    def join(self, timeout=None, raise_error=False):
        timeout = Timeout.start_new(timeout)
        try:
            try:
                while self.greenlets:
                    joinall(self.greenlets, raise_error=raise_error)
            except Timeout, ex:
                if ex is not timeout:
                    raise
        finally:
            timeout.cancel()

    def kill(self, exception=GreenletExit, block=False, timeout=None):
        t = Timeout.start_new(timeout)
        try:
            while self.greenlets:
                for p in self.greenlets:
                    if p not in self.dying:
                        p.kill(exception)
                        self.dying.add(p)
                if not block:
                    break
                joinall(self.greenlets)
        finally:
            t.cancel()

    def killone(self, p, exception=GreenletExit, block=False, timeout=None):
        if p not in self.dying and p in self.greenlets:
            p.kill(exception)
            self.dying.add(p)
            if block:
                p.join(timeout)

    def apply(self, func, args=None, kwds=None):
        """Equivalent of the apply() builtin function. It blocks till the result is ready."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        if getcurrent() in self:
            return func(*args, **kwds)
        else:
            return self.spawn(func, *args, **kwds).get()

    def apply_async(self, func, args=None, kwds=None, callback=None):
        """A variant of the apply() method which returns a Greenlet object.

        If callback is specified then it should be a callable which accepts a single argument. When the result becomes ready
        callback is applied to it (unless the call failed)."""
        if args is None:
            args = ()
        if kwds is None:
            kwds = {}
        p = self.spawn(func, *args, **kwds)
        if callback is not None:
            p.link(pass_value(callback))
        return p

    def map(self, func, iterable):
        greenlets = [self.spawn(func, item) for item in iterable]
        return [g.get() for g in greenlets]

    def map_async(self, func, iterable, callback=None):
        """
        A variant of the map() method which returns a Greenlet object.

        If callback is specified then it should be a callable which accepts a
        single argument.
        """
        greenlets = [self.spawn(func, item) for item in iterable]
        result = self.spawn(get_values, greenlets)
        if callback is not None:
            result.link(pass_value(callback))
        return result

    def imap(self, func, iterable):
        """An equivalent of itertools.imap()"""
        greenlets = [self.spawn(func, item) for item in iterable]
        for g in greenlets:
            yield g.get()

    def imap_unordered(self, func, iterable):
        """The same as imap() except that the ordering of the results from the
        returned iterator should be considered arbitrary."""
        from gevent.queue import Queue
        q = Queue()
        greenlets = [self.spawn(func, item) for item in iterable]
        for g in greenlets:
            g.rawlink(q.put)
        for _ in xrange(len(greenlets)):
            yield q.get().get()
    
    def full(self):
        return False


class Pool(GreenletSet):

    def __init__(self, size=None):
        if size is not None and size < 0:
            raise ValueError('Invalid size for pool (positive integer or None required): %r' % (size, ))
        GreenletSet.__init__(self)
        self.size = size
        self.waiting = deque()

    def full(self):
        return self.free_count() <= 0

    def free_count(self):
        if self.size is None:
            return 1
        return max(0, self.size - len(self) - len(self.waiting))

    def start(self, g):
        if self.size is not None and len(self) >= self.size:
            self.waiting.append(g)
        else:
            g.start()
            self.add(g)

    def spawn(self, function, *args, **kwargs):
        g = Greenlet(function, *args, **kwargs)
        self.start(g)
        return g

    def discard(self, p):
        GreenletSet.discard(self, p)
        while self.waiting and len(self) < self.size:
            g = self.waiting.popleft()
            g.start()
            self.add(g)

    def kill(self, exception=GreenletExit, block=False, timeout=None):
        for g in self.waiting:
            g.kill(exception)
        self.waiting.clear()
        return GreenletSet.kill(self, exception=exception, block=block, timeout=timeout)


def get_values(greenlets):
    joinall(greenlets)
    return [x.value for x in greenlets]


class pass_value(object):
    __slots__ = ['callback']

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, source):
        if source.successful():
            self.callback(source.value)

    def __hash__(self):
        return hash(self.callback)

    def __eq__(self, other):
        return self.callback == getattr(other, 'callback', other)

    def __str__(self):
        return str(self.callback)

    def __repr__(self):
        return repr(self.callback)

    def __getattr__(self, item):
        assert item != 'callback'
        return getattr(self.callback, item)

