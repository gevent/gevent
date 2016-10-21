# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
"""Locking primitives"""
from __future__ import absolute_import

from gevent.hub import getcurrent
from gevent._compat import PYPY
from gevent._semaphore import Semaphore, BoundedSemaphore # pylint:disable=no-name-in-module,import-error


__all__ = [
    'Semaphore',
    'DummySemaphore',
    'BoundedSemaphore',
    'RLock',
]

# On PyPy, we don't compile the Semaphore class with Cython. Under
# Cython, each individual method holds the GIL for its entire
# duration, ensuring that no other thread can interrupt us in an
# unsafe state (only when we _do_wait do we call back into Python and
# allow switching threads). Simulate that here through the use of a manual
# lock. (We use a separate lock for each semaphore to allow sys.settrace functions
# to use locks *other* than the one being traced.)
if PYPY:
    # TODO: Need to use monkey.get_original?
    try:
        from _thread import allocate_lock as _allocate_lock # pylint:disable=import-error,useless-suppression
        from _thread import get_ident as _get_ident # pylint:disable=import-error,useless-suppression
    except ImportError:
        # Python 2
        from thread import allocate_lock as _allocate_lock # pylint:disable=import-error,useless-suppression
        from thread import get_ident as _get_ident # pylint:disable=import-error,useless-suppression
    _sem_lock = _allocate_lock()

    def untraceable(f):
        # Don't allow re-entry to these functions in a single thread, as can
        # happen if a sys.settrace is used
        def wrapper(self):
            me = _get_ident()
            try:
                count = self._locking[me]
            except KeyError:
                count = self._locking[me] = 1
            else:
                count = self._locking[me] = count + 1
            if count:
                return

            try:
                return f(self)
            finally:
                count = count - 1
                if not count:
                    del self._locking[me]
                else:
                    self._locking[me] = count
        return wrapper

    class _OwnedLock(object):

        def __init__(self):
            self._owner = None
            self._block = _allocate_lock()
            self._locking = {}
            self._count = 0

        @untraceable
        def acquire(self):
            me = _get_ident()
            if self._owner == me:
                self._count += 1
                return

            self._owner = me
            self._block.acquire()
            self._count = 1

        @untraceable
        def release(self):
            self._count = count = self._count - 1
            if not count:
                self._block.release()
                self._owner = None

    # acquire, wait, and release all acquire the lock on entry and release it
    # on exit. acquire and wait can call _do_wait, which must release it on entry
    # and re-acquire it for them on exit.
    class _around(object):
        __slots__ = ('before', 'after')

        def __init__(self, before, after):
            self.before = before
            self.after = after

        def __enter__(self):
            self.before()

        def __exit__(self, t, v, tb):
            self.after()

    def _decorate(func, cmname):
        # functools.wrap?
        def wrapped(self, *args, **kwargs):
            with getattr(self, cmname):
                return func(self, *args, **kwargs)
        return wrapped

    Semaphore._py3k_acquire = Semaphore.acquire = _decorate(Semaphore.acquire, '_lock_locked')
    Semaphore.release = _decorate(Semaphore.release, '_lock_locked')
    Semaphore.wait = _decorate(Semaphore.wait, '_lock_locked')
    Semaphore._do_wait = _decorate(Semaphore._do_wait, '_lock_unlocked')

    _Sem_init = Semaphore.__init__

    def __init__(self, *args, **kwargs):
        l = self._lock_lock = _OwnedLock()
        self._lock_locked = _around(l.acquire, l.release)
        self._lock_unlocked = _around(l.release, l.acquire)

        _Sem_init(self, *args, **kwargs)

    Semaphore.__init__ = __init__

    del _decorate
    del untraceable


class DummySemaphore(object):
    """
    DummySemaphore(value=None) -> DummySemaphore

    A Semaphore initialized with "infinite" initial value. None of its
    methods ever block.

    This can be used to parameterize on whether or not to actually
    guard access to a potentially limited resource. If the resource is
    actually limited, such as a fixed-size thread pool, use a real
    :class:`Semaphore`, but if the resource is unbounded, use an
    instance of this class. In that way none of the supporting code
    needs to change.

    Similarly, it can be used to parameterize on whether or not to
    enforce mutual exclusion to some underlying object. If the
    underlying object is known to be thread-safe itself mutual
    exclusion is not needed and a ``DummySemaphore`` can be used, but
    if that's not true, use a real ``Semaphore``.
    """

    # Internally this is used for exactly the purpose described in the
    # documentation. gevent.pool.Pool uses it instead of a Semaphore
    # when the pool size is unlimited, and
    # gevent.fileobject.FileObjectThread takes a parameter that
    # determines whether it should lock around IO to the underlying
    # file object.

    def __init__(self, value=None):
        """
        .. versionchanged:: 1.1rc3
            Accept and ignore a *value* argument for compatibility with Semaphore.
        """
        pass

    def __str__(self):
        return '<%s>' % self.__class__.__name__

    def locked(self):
        """A DummySemaphore is never locked so this always returns False."""
        return False

    def release(self):
        """Releasing a dummy semaphore does nothing."""
        pass

    def rawlink(self, callback):
        # XXX should still work and notify?
        pass

    def unlink(self, callback):
        pass

    def wait(self, timeout=None):
        """Waiting for a DummySemaphore returns immediately."""
        pass

    def acquire(self, blocking=True, timeout=None):
        """
        A DummySemaphore can always be acquired immediately so this always
        returns True and ignores its arguments.

        .. versionchanged:: 1.1a1
           Always return *true*.
        """
        # pylint:disable=unused-argument
        return True

    def __enter__(self):
        pass

    def __exit__(self, typ, val, tb):
        pass


class RLock(object):

    def __init__(self):
        self._block = Semaphore(1)
        self._owner = None
        self._count = 0

    def __repr__(self):
        return "<%s at 0x%x _block=%s _count=%r _owner=%r)>" % (
            self.__class__.__name__,
            id(self),
            self._block,
            self._count,
            self._owner)

    def acquire(self, blocking=1):
        me = getcurrent()
        if self._owner is me:
            self._count = self._count + 1
            return 1
        rc = self._block.acquire(blocking)
        if rc:
            self._owner = me
            self._count = 1
        return rc

    def __enter__(self):
        return self.acquire()

    def release(self):
        if self._owner is not getcurrent():
            raise RuntimeError("cannot release un-aquired lock")
        self._count = count = self._count - 1
        if not count:
            self._owner = None
            self._block.release()

    def __exit__(self, typ, value, tb):
        self.release()

    # Internal methods used by condition variables

    def _acquire_restore(self, count_owner):
        count, owner = count_owner
        self._block.acquire()
        self._count = count
        self._owner = owner

    def _release_save(self):
        count = self._count
        self._count = 0
        owner = self._owner
        self._owner = None
        self._block.release()
        return (count, owner)

    def _is_owned(self):
        return self._owner is getcurrent()
