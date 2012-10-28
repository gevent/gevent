import sys
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout


__all__ = ['Semaphore']


class Semaphore(object):
    """A semaphore manages a counter representing the number of release() calls minus the number of acquire() calls,
    plus an initial value. The acquire() method blocks if necessary until it can return without making the counter
    negative.

    If not given, value defaults to 1.

    This Semaphore's __exit__ method does not call the trace function.
    """

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")
        self._links = []
        self.counter = value
        self._notifier = None
        # we don't want to do get_hub() here to allow module-level locks
        # without initializing the hub

    def __str__(self):
        params = (self.__class__.__name__, self.counter, len(self._links))
        return '<%s counter=%s _links[%s]>' % params

    def locked(self):
        return self.counter <= 0

    def release(self):
        self.counter += 1
        self._start_notify()

    def _start_notify(self):
        if self._links and self.counter > 0 and not self._notifier:
            self._notifier = get_hub().loop.run_callback(self._notify_links)

    def _notify_links(self):
        while True:
            self._dirty = False
            for link in self._links:
                if self.counter <= 0:
                    return
                try:
                    link(self)
                except:
                    getcurrent().handle_error((link, self), *sys.exc_info())
                if self._dirty:
                    break
            if not self._dirty:
                return

    def rawlink(self, callback):
        """Register a callback to call when a counter is more than zero.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.append(callback)
        self._dirty = True

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
            self._dirty = True
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
                    except Timeout:
                        ex = sys.exc_info()[1]
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
                    except Timeout:
                        ex = sys.exc_info()[1]
                        if ex is timer:
                            return False
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

    def __exit__(self, *args):
        self.release()
