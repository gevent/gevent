# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.

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
            for greenlet in args[0]:
                greenlet.rawlink(self.discard)
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

    def add(self, greenlet):
        greenlet.rawlink(self.discard)
        self.greenlets.add(greenlet)

    def discard(self, greenlet):
        self.greenlets.discard(greenlet)
        self.dying.discard(greenlet)

    def spawn(self, *args, **kwargs):
        add = self.add
        greenlet = self.greenlet_class.spawn(*args, **kwargs)
        add(greenlet)
        return greenlet

    def spawn_link(self, *args, **kwargs):
        greenlet = self.spawn(*args, **kwargs)
        greenlet.link()
        return greenlet

    def spawn_link_value(self, *args, **kwargs):
        greenlet = self.spawn(*args, **kwargs)
        greenlet.link_value()
        return greenlet

    def spawn_link_exception(self, *args, **kwargs):
        greenlet = self.spawn(*args, **kwargs)
        greenlet.link_exception()
        return greenlet

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
        timer = Timeout.start_new(timeout)
        try:
            while self.greenlets:
                for greenlet in self.greenlets:
                    if greenlet not in self.dying:
                        greenlet.kill(exception)
                        self.dying.add(greenlet)
                if not block:
                    break
                joinall(self.greenlets)
        finally:
            timer.cancel()

    def killone(self, greenlet, exception=GreenletExit, block=False, timeout=None):
        if greenlet not in self.dying and greenlet in self.greenlets:
            greenlet.kill(exception)
            self.dying.add(greenlet)
            if block:
                greenlet.join(timeout)

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
        greenlet = self.spawn(func, *args, **kwds)
        if callback is not None:
            greenlet.link(pass_value(callback))
        return greenlet

    def map(self, func, iterable):
        greenlets = [self.spawn(func, item) for item in iterable]
        return [greenlet.get() for greenlet in greenlets]

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
        for greenlet in greenlets:
            yield greenlet.get()

    def imap_unordered(self, func, iterable):
        """The same as imap() except that the ordering of the results from the
        returned iterator should be considered arbitrary."""
        from gevent.queue import Queue
        q = Queue()
        greenlets = [self.spawn(func, item) for item in iterable]
        for greenlet in greenlets:
            greenlet.rawlink(q.put)
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

    def start(self, greenlet):
        if self.size is not None and len(self) >= self.size:
            self.waiting.append(greenlet)
        else:
            greenlet.start()
            self.add(greenlet)

    def spawn(self, function, *args, **kwargs):
        greenlet = Greenlet(function, *args, **kwargs)
        self.start(greenlet)
        return greenlet

    def discard(self, greenlet):
        GreenletSet.discard(self, greenlet)
        while self.waiting and len(self) < self.size:
            greenlet = self.waiting.popleft()
            greenlet.start()
            self.add(greenlet)

    def kill(self, exception=GreenletExit, block=False, timeout=None):
        for greenlet in self.waiting:
            greenlet.kill(exception)
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

