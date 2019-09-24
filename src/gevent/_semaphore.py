# cython: auto_pickle=False,embedsignature=True,always_allow_keywords=False
from __future__ import print_function, absolute_import, division

__all__ = [
    'Semaphore',
    'BoundedSemaphore',
]

def _get_linkable():
    x = __import__('gevent._abstract_linkable')
    return x._abstract_linkable.AbstractLinkable
locals()['AbstractLinkable'] = _get_linkable()
del _get_linkable


class Semaphore(AbstractLinkable): # pylint:disable=undefined-variable
    """
    Semaphore(value=1) -> Semaphore

    A semaphore manages a counter representing the number of release()
    calls minus the number of acquire() calls, plus an initial value.
    The acquire() method blocks if necessary until it can return
    without making the counter negative.

    If not given, ``value`` defaults to 1.

    The semaphore is a context manager and can be used in ``with`` statements.

    This Semaphore's ``__exit__`` method does not call the trace function
    on CPython, but does under PyPy.

    .. seealso:: :class:`BoundedSemaphore` for a safer version that prevents
       some classes of bugs.

    .. versionchanged:: 1.4.0

        The order in which waiters are awakened is not specified. It was not
        specified previously, but usually went in FIFO order.
    """

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")
        super(Semaphore, self).__init__()
        self.counter = value
        self._notify_all = False

    def __str__(self):
        params = (self.__class__.__name__, self.counter, self.linkcount())
        return '<%s counter=%s _links[%s]>' % params

    def locked(self):
        """Return a boolean indicating whether the semaphore can be acquired.
        Most useful with binary semaphores."""
        return self.counter <= 0

    def release(self):
        """
        Release the semaphore, notifying any waiters if needed.
        """
        self.counter += 1
        self._check_and_notify()
        return self.counter

    def ready(self):
        return self.counter > 0

    def _start_notify(self):
        self._check_and_notify()

    def _wait_return_value(self, waited, wait_success):
        if waited:
            return wait_success
        # We didn't even wait, we must be good to go.
        # XXX: This is probably dead code, we're careful not to go into the wait
        # state if we don't expect to need to
        return True

    def wait(self, timeout=None):
        """
        wait(timeout=None) -> int

        Wait until it is possible to acquire this semaphore, or until the optional
        *timeout* elapses.

        .. caution:: If this semaphore was initialized with a size of 0,
           this method will block forever if no timeout is given.

        :keyword float timeout: If given, specifies the maximum amount of seconds
           this method will block.
        :return: A number indicating how many times the semaphore can be acquired
            before blocking.
        """
        if self.counter > 0:
            return self.counter

        self._wait(timeout) # return value irrelevant, whether we got it or got a timeout
        return self.counter

    def acquire(self, blocking=True, timeout=None):
        """
        acquire(blocking=True, timeout=None) -> bool

        Acquire the semaphore.

        .. caution:: If this semaphore was initialized with a size of 0,
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
            success = self._wait(0)
        else:
            success = self._wait(timeout)

        if not success:
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
    BoundedSemaphore(value=1) -> BoundedSemaphore

    A bounded semaphore checks to make sure its current value doesn't
    exceed its initial value. If it does, :class:`ValueError` is
    raised. In most situations semaphores are used to guard resources
    with limited capacity. If the semaphore is released too many times
    it's a sign of a bug.

    If not given, *value* defaults to 1.
    """

    #: For monkey-patching, allow changing the class of error we raise
    _OVER_RELEASE_ERROR = ValueError

    def __init__(self, *args, **kwargs):
        Semaphore.__init__(self, *args, **kwargs)
        self._initial_value = self.counter

    def release(self):
        if self.counter >= self._initial_value:
            raise self._OVER_RELEASE_ERROR("Semaphore released too many times")
        Semaphore.release(self)



# By building the semaphore with Cython under PyPy, we get
# atomic operations (specifically, exiting/releasing), at the
# cost of some speed (one trivial semaphore micro-benchmark put the pure-python version
# at around 1s and the compiled version at around 4s). Some clever subclassing
# and having only the bare minimum be in cython might help reduce that penalty.
# NOTE: You must use version 0.23.4 or later to avoid a memory leak.
# https://mail.python.org/pipermail/cython-devel/2015-October/004571.html
# However, that's all for naught on up to and including PyPy 4.0.1 which
# have some serious crashing bugs with GC interacting with cython.
# It hasn't been tested since then, and PURE_PYTHON is assumed to be true
# for PyPy in all cases anyway, so this does nothing.

from gevent._util import import_c_accel
import_c_accel(globals(), 'gevent.__semaphore')
