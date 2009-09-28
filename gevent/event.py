# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.
"""Basic synchronization primitives: Event and AsyncResult.

Event implements threading.Event interface but works across greenlets not threads.
AsyncResult is a one-time Event that stores a result: value or exception.
"""

import sys
import traceback
from gevent import core
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout, _NONE


class Event(object):
    """A synchronization primitive that allows one greenlet to wake up one or more others"""

    def __init__(self):
        self._links = []
        self._flag = False

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, (self._flag and 'set') or 'clear')

    def is_set(self):
        return self._flag

    isSet = is_set # makes it a better drop-in replacement for threading.Event

    def rawlink(self, callback):
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.append(callback)
        if self._flag:
            core.active_event(self._notify_links, list(self._links))

    def unlink(self, callback):
        try:
            self._links.remove(callback)
        except ValueError:
            pass

    def clear(self):
        """Clear the internal flag.
        Subsequently, greenlets calling wait() will block until set() is called.
        """
        self._flag = False

    def set(self):
        self._flag = True
        if self._links:
            # schedule a job to notify the links already set
            core.active_event(self._notify_links, list(self._links))

    def _notify_links(self, links):
        assert getcurrent() is get_hub()
        for link in links:
            if link in self._links: # check that link was not notified yet and was not removed by the client
                try:
                    link(self)
                except:
                    traceback.print_exc()
                    try:
                        sys.stderr.write('Failed to notify link %r of %r\n\n' % (link, self))
                    except:
                        pass

    def wait(self, timeout=None):
        if self._flag:
            return
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Event.wait(): %r' % (result, )
                except Timeout, exc:
                    if exc is not t:
                        raise
                finally:
                    t.cancel()
            finally:
                self.unlink(switch)


class AsyncResult(object):
    """A one-time Event that stores a value or an exception.
    
    AsyncResult can be used to pass a value or exception to one or more waiters.
    Its set() method accepts an argument - value to store. The sequential calls
    to get() method will return the value passed:

        >>> result = AsyncResult()
        >>> result.set(100)
        >>> result.get()
        100

    Additionally, it has set_exception() method, that causes get() to raise an error:

        >>> result = AsyncResult()
        >>> result.set_exception(RuntimeError('failure'))
        >>> result.get()
        Traceback (most recent call last):
         ...
        RuntimeError: failure

    Similar to multiprocessing.AsyncResult, ready() and successful() methods are available.
    Similar to Greenlet, AsyncResult has 'value' and 'exception' properties.
    
    AsyncResult instance can be used as link() target:

        >>> result = AsyncResult()
        >>> gevent.spawn(lambda : 1/0).link(result)
        >>> result.get()
        Traceback (most recent call last):
         ...
        ZeroDivisionError: integer division or modulo by zero
    """
    def __init__(self):
        self._links = set()
        self.value = None
        self._exception = _NONE
        self._notifier = None

    def ready(self):
        return self._exception is not _NONE

    def successful(self):
        return self._exception is None

    @property
    def exception(self):
        if self._exception is not _NONE:
            return self._exception

    def rawlink(self, callback):
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.add(callback)
        if self.ready() and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def unlink(self, callback):
        self._links.discard(callback)

    def set(self, value=None):
        self.value = value
        self._exception = None
        if self._links and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def set_exception(self, exception):
        self._exception = exception
        if self._links and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def _notify_links(self):
        try:
            assert getcurrent() is get_hub()
            while self._links:
                link = self._links.pop()
                try:
                    link(self)
                except:
                    traceback.print_exc()
                    try:
                        sys.stderr.write('Failed to notify link %r of %r\n\n' % (link, self))
                    except:
                        pass
        finally:
            self._notifier = None

    def get(self, block=True, timeout=None):
        if self._exception is not _NONE:
            if self._exception is None:
                return self.value
            raise self._exception
        elif block:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into AsyncResult.get(): %r' % (result, )
                finally:
                    t.cancel()
            except:
                self.unlink(switch)
                raise
            if self._exception is None:
                return self.value
            raise self._exception
        else:
            raise Timeout

    def get_nowait(self):
        return self.get(block=False)

    def wait(self, timeout=None):
        if self._exception is not _NONE:
            return
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into AsyncResult.wait(): %r' % (result, )
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

    # link protocol
    def __call__(self, source):
        if source.successful():
            self.set(source.value)
        else:
            self.set_exception(source.exception)


def waitall(events):
    # QQQ add timeout?
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

