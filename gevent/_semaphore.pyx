import sys
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout


__all__ = ['Semaphore', 'BoundedSemaphore']



class Semaphore(object):
    """
    A semaphore manages a counter representing the number of release()
    calls minus the number of acquire() calls, plus an initial value.
    The acquire() method blocks if necessary until it can return
    without making the counter negative.

    If not given, ``value`` defaults to 1.

    This Semaphore's ``__exit__`` method does not call the trace function.
    """

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")
        self._links = []
        self.counter = value
        self._notifier = None
        self._dirty = False
        # we don't want to do get_hub() here to allow module-level locks
        # without initializing the hub

    def __str__(self):
        params = (self.__class__.__name__, self.counter, len(self._links))
        return '<%s counter=%s _links[%s]>' % params

    def locked(self):
        """Return a boolean indicating whether the semaphore can be acquired.
        Most useful with binary semaphores."""
        return self.counter <= 0

    def release(self):
        self.counter += 1
        self._start_notify()
        return self.counter

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
        """
        Wait until it is possible to acquire this semaphore, or until the optional
        *timeout* elapses.

        .. warning:: If this semaphore was initialized with a size of 0,
           this method will block forever if no timeout is given.

        :param float timeout: If given, specifies the maximum amount of seconds
           this method will block.
        :return: A number indicating how many times the semaphore can be acquired
            before blocking.
        """
        if self.counter > 0:
            return self.counter

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
        """
        Acquire the semaphore.

        .. warning:: If this semaphore was initialized with a size of 0,
           this method will block forever (unless a timeout is given or blocking is
           set to false).

        :keyword bool blocking: If True (the default), this function will block
           until the semaphore is acquired.
        :keyword float timeout: If given, specifies the maximum amount of seconds
           this method will block.
        :return: A boolean indicating whether the semaphore was acquired.
           If ``blocking`` is True and ``timeout`` is None (the default), then
           (so long as this semaphore was initialized with a size greater than 0)
           this will always return True. If a timeout was given, and it expired before
           the semaphore was acquired, False will be returned.
        """
        if self.counter > 0:
            self.counter -= 1
            return True

        if not blocking:
            return False

        switch = getcurrent().switch
        self.rawlink(switch)
        try:
            # As a tiny efficiency optimization, avoid allocating a timer
            # if not needed.
            timer = Timeout.start_new(timeout) if timeout is not None else None
            try:
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Semaphore.acquire(): %r' % (result, )
                except Timeout as ex:
                    if ex is timer:
                        return False
                    raise
            finally:
                if timer is not None:
                    timer.cancel()
        finally:
            self.unlink(switch)
        self.counter -= 1
        assert self.counter >= 0
        return True

    _py3k_acquire = acquire # PyPy needs this; it must be static for Cython

    def __enter__(self):
        self.acquire()

    def __exit__(self, t, v, tb):
        self.release()

class BoundedSemaphore(Semaphore):
    """
    A bounded semaphore checks to make sure its current value doesn't
    exceed its initial value. If it does, :class:`ValueError` is
    raised. In most situations semaphores are used to guard resources
    with limited capacity. If the semaphore is released too many times
    it's a sign of a bug.

    If not given, *value* defaults to 1.
    """

    _OVER_RELEASE_ERROR = ValueError

    def __init__(self, value=1):
        Semaphore.__init__(self, value)
        self._initial_value = value

    def release(self):
        if self.counter >= self._initial_value:
            raise self._OVER_RELEASE_ERROR("Semaphore released too many times")
        return Semaphore.release(self)
