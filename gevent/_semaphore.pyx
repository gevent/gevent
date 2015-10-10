import sys
from gevent.hub import get_hub, getcurrent
from gevent.timeout import Timeout


__all__ = ['Semaphore', 'BoundedSemaphore']


class Semaphore(object):
    """
    Semaphore(value=1) -> Semaphore

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
        self.counter = value
        self._dirty = False
        # In PyPy 2.6.1 with Cython 0.23, `cdef public` or `cdef
        # readonly` or simply `cdef` attributes of type `object` can appear to leak if
        # a Python subclass is used (this is visible simply
        # instantiating this subclass if _links=[]). Our _links and
        # _notifier are such attributes, and gevent.thread subclasses
        # this class. Thus, we carefully manage the lifetime of the
        # objects we put in these attributes so that, in the normal
        # case of a semaphore used correctly (dealloced when it's not
        # locked and no one is waiting), the leak goes away (because
        # these objects are back to None). This can also be solved on PyPy
        # by simply not declaring these objects in the pxd file, but that doesn't work for
        # CPython ("No attribute...")
        # See https://github.com/gevent/gevent/issues/660
        self._links = None
        self._notifier = None
        # we don't want to do get_hub() here to allow defining module-level locks
        # without initializing the hub

    def __str__(self):
        params = (self.__class__.__name__, self.counter, len(self._links) if self._links else 0)
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
            # We create a new self._notifier each time through the loop,
            # if needed. (it has a __bool__ method that tells whether it has
            # been run; once it's run once---at the end of the loop---it becomes
            # false.)
            # NOTE: Passing the bound method will cause a memory leak on PyPy
            # with Cython <= 0.23.3. You must use >= 0.23.4.
            # See  https://bitbucket.org/pypy/pypy/issues/2149/memory-leak-for-python-subclass-of-cpyext#comment-22371546
            self._notifier = get_hub().loop.run_callback(self._notify_links)

    def _notify_links(self):
        # Subclasses CANNOT override. This is a cdef method.

        # We release self._notifier here. We are called by it
        # at the end of the loop, and it is now false in a boolean way (as soon
        # as this method returns).
        # If we get acquired/released again, we will create a new one, but there's
        # no need to keep it around until that point (making it potentially climb
        # into older GC generations, notably on PyPy)
        notifier = self._notifier
        try:
            while True:
                self._dirty = False
                if not self._links:
                    # In case we were manually unlinked before
                    # the callback. Which shouldn't happen
                    return
                for link in self._links:
                    if self.counter <= 0:
                        return
                    try:
                        link(self) # Must use Cython >= 0.23.4 on PyPy else this leaks memory
                    except:
                        getcurrent().handle_error((link, self), *sys.exc_info())
                    if self._dirty:
                        # We mutated self._links so we need to start over
                        break
                if not self._dirty:
                    return
        finally:
            # We should not have created a new notifier even if callbacks
            # released us because we loop through *all* of our links on the
            # same callback while self._notifier is still true.
            assert self._notifier is notifier
            self._notifier = None

    def rawlink(self, callback):
        """
        rawlink(callback) -> None

        Register a callback to call when a counter is more than zero.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable:', callback)
        if self._links is None:
            self._links = [callback]
        else:
            self._links.append(callback)
        self._dirty = True

    def unlink(self, callback):
        """
        unlink(callback) -> None

        Remove the callback set by :meth:`rawlink`
        """
        try:
            self._links.remove(callback)
            self._dirty = True
        except (ValueError, AttributeError):
            pass
        if not self._links:
            self._links = None
            # TODO: Cancel a notifier if there are no links?

    def _do_wait(self, timeout):
        """
        Wait for up to *timeout* seconds to expire. If timeout
        elapses, return the exception. Otherwise, return None.
        Raises timeout if a different timer expires.
        """
        switch = getcurrent().switch
        self.rawlink(switch)
        try:
            # As a tiny efficiency optimization, avoid allocating a timer
            # if not needed.
            timer = Timeout.start_new(timeout) if timeout is not None else None
            try:
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Semaphore.wait/acquire(): %r' % (result, )
                except Timeout as ex:
                    if ex is not timer:
                        raise
                    return ex
            finally:
                if timer is not None:
                    timer.cancel()
        finally:
            self.unlink(switch)

    def wait(self, timeout=None):
        """
        wait(timeout=None) -> int

        Wait until it is possible to acquire this semaphore, or until the optional
        *timeout* elapses.

        .. warning:: If this semaphore was initialized with a size of 0,
           this method will block forever if no timeout is given.

        :keyword float timeout: If given, specifies the maximum amount of seconds
           this method will block.
        :return: A number indicating how many times the semaphore can be acquired
            before blocking.
        """
        if self.counter > 0:
            return self.counter

        self._do_wait(timeout) # return value irrelevant, whether we got it or got a timeout
        return self.counter

    def acquire(self, blocking=True, timeout=None):
        """
        acquire(blocking=True, timeout=None) -> bool

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
           the semaphore was acquired, False will be returned. (Note that this can still
           raise a ``Timeout`` exception, if some other caller had already started a timer.)
        """
        if self.counter > 0:
            self.counter -= 1
            return True

        if not blocking:
            return False

        timeout = self._do_wait(timeout)
        if timeout is not None:
            # Our timer expired.
            return False

        # Neither our timer no another one expired, so we blocked until
        # awoke. Therefore, the counter is ours
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
