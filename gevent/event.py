# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

import sys
import traceback
from gevent import core
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout


class Event(object):

    def __init__(self):
        self._links = set()
        self._value = _NONE
        self._notifier = None

    def is_set(self):
        return self._value is not _NONE

    isSet = is_set
    ready = is_set

    @property
    def value(self):
        if self._value is not _NONE:
            return self._value

    def rawlink(self, callback):
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.add(callback)
        if self.ready() and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def unlink(self, callback):
        self._links.discard(callback)

    def clear(self):
        """Reset the internal state. Subsequently, greenlets calling wait() or get()
        will block until set() or put() is called.

        Greenlets that called get() and wait() before clear() but were not yet notified
        since the last put() call will _not_ be notified.
        """
        self._value = _NONE

    def set(self, value=None):
        oldvalue = self._value
        self._value = value
        if oldvalue is _NONE:
            if self._links and self._notifier is None:
                self._notifier = core.active_event(self._notify_links)

    def _notify_links(self):
        try:
            assert getcurrent() is get_hub()
            while self._links and self._value is not _NONE:
                link = self._links.pop()
                try:
                    link(self)
                except:
                    traceback.print_exc()
                    try:
                        sys.stderr.write('Failed to notify link %r of %r\n\n' % (link, self))
                    except:
                        pass
                # even if g is left unscheduled, it will be deallocated because there are no more references to it
        finally:
            self._notifier = None

    def get(self, block=True, timeout=None):
        if self._value is not _NONE:
            return self._value
        elif block:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Event.get(): %r' % (result, )
                finally:
                    t.cancel()
            except:
                self.unlink(switch)
                raise
            return self._value
        else:
            raise Timeout

    def get_nowait(self):
        return self.get(block=False)

    def wait(self, timeout=None):
        if self._value is not _NONE:
            return
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Event.wait(): %r' % (result, )
                finally:
                    t.cancel()
            except Timeout, exc:
                self.unlink(switch)
                if exc is not t:
                    raise
            except:
                self.unlink(switch)
                raise
            # not calling unlink() in non-exception case, because if switch()
            # finished normally, link was already removed in _notify_links

    def put(self, value=None):
        import warnings
        warnings.warn("Event.put is deprecated; use Event.set", DeprecationWarning, stacklevel=2)
        return self.set(value=value)
    

class AsyncResult(Event):
    """Like Greenlet, has 'value' and 'exception' properties, successful() method and get() can raise.

    Unlike Event and Queue, AsyncResult instances can be used as link() targets:

    >>> import gevent
    >>> r = AsyncResult()
    >>> gevent.spawn(lambda : 1/0).link(r)
    >>> r.get()
    Traceback (most recent call last):
     ...
    ZeroDivisionError: integer division or modulo by zero
    """

    @property
    def value(self):
        if self.ready():
            result, exception = Event.get(self)
            return result

    @property
    def exception(self):
        if self.ready():
            result, exception = Event.get(self)
            return exception

    def get(self, block=True, timeout=None):
        result, exception = Event.get(self, block=block, timeout=timeout)
        if exception is None:
            return result
        else:
            raise exception

    def successful(self):
        result, exception = self._value
        return exception is None

    def set(self, value):
        return Event.set(self, (value, None))

    def set_exception(self, exception):
        return Event.set(self, (None, exception))

    def __call__(self, source):
        if source.successful():
            self.set(source.value)
        else:
            self.set_exception(source.exception)

    def put(self, value):
        import warnings
        warnings.warn("AsyncResult.put is deprecated; use AsyncResult.set", DeprecationWarning, stacklevel=2)
        return self.set(value)

    def put_exception(self, exception):
        import warnings
        warnings.warn("AsyncResult.put_exception is deprecated; use AsyncResult.set_exception", DeprecationWarning, stacklevel=2)
        return self.set_exception(exception)
    # QQQ add link_value and link_exception here?


def waitall(events):
    from gevent.queue import Queue
    queue = Queue()
    put = queue.put
    try:
        for event in events:
            event.rawlink(put)
        for _ in xrange(len(events)):
            queue.get()
    finally:
        for event in events:
            event.unlink(put)


_NONE = object()

