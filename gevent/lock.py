# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
"""Locking primitives"""

from gevent.hub import getcurrent, sleep
from gevent._semaphore import Semaphore
from gevent._threading import get_ident, local


__all__ = ['Semaphore', 'DummySemaphore', 'BoundedSemaphore', 'RLock', 'NativeFriendlyRLock']


class DummySemaphore(object):
    # XXX what is this used for?
    """A Semaphore initialized with "infinite" initial value. None of its methods ever block."""

    def __str__(self):
        return '<%s>' % self.__class__.__name__

    def locked(self):
        return False

    def release(self):
        pass

    def rawlink(self, callback):
        # XXX should still work and notify?
        pass

    def unlink(self, callback):
        pass

    def wait(self, timeout=None):
        pass

    def acquire(self, blocking=True, timeout=None):
        pass

    def __enter__(self):
        pass

    def __exit__(self, typ, val, tb):
        pass


class BoundedSemaphore(Semaphore):
    """A bounded semaphore checks to make sure its current value doesn't exceed its initial value.
    If it does, ``ValueError`` is raised. In most situations semaphores are used to guard resources
    with limited capacity. If the semaphore is released too many times it's a sign of a bug.

    If not given, *value* defaults to 1."""

    def __init__(self, value=1):
        Semaphore.__init__(self, value)
        self._initial_value = value

    def release(self):
        if self.counter >= self._initial_value:
            raise ValueError("Semaphore released too many times")
        return Semaphore.release(self)


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


class NativeFriendlyRLock(object):
    def __init__(self):
        self._thread_local = local()
        self._owner = None
        self._wait_queue = []
        self._count = 0

    def __repr__(self):
        owner = self._owner
        return "<%s owner=%r count=%d>" % (self.__class__.__name__, owner, self._count)

    def acquire(self, blocking=1):
        tid = get_ident()
        gid = id(getcurrent())
        tid_gid = (tid, gid)
        if tid_gid == self._owner:  # We trust the GIL here so we can do this comparison w/o locking.
            self._count = self._count + 1
            return True

        greenlet_lock = self._get_greenlet_lock()

        self._wait_queue.append(gid)
        # this is a safety in case an exception is raised somewhere and we must make sure we're not in the queue
        # otherwise it'll get stuck forever.
        remove_from_queue_on_return = True
        try:
            while True:
                if not greenlet_lock.acquire(blocking):
                    return False  # non-blocking and failed to acquire lock

                if self._wait_queue[0] == gid:
                    # Hurray, we can have the lock.
                    self._owner = tid_gid
                    self._count = 1
                    remove_from_queue_on_return = False  # don't remove us from the queue
                    return True
                else:
                    # we already hold the greenlet lock so obviously the owner is not in our thread.
                    greenlet_lock.release()
                    if blocking:
                        sleep(0.0005)  # 500 us -> initial delay of 1 ms
                    else:
                        return False
        finally:
            if remove_from_queue_on_return:
                self._wait_queue.remove(gid)

    def release(self):
        tid_gid = (get_ident(), id(getcurrent()))
        if tid_gid != self._owner:
            raise RuntimeError("cannot release un-acquired lock")

        self._count = self._count - 1
        if not self._count:
            self._owner = None
            gid = self._wait_queue.pop(0)
            assert gid == tid_gid[1]
            self._thread_local.greenlet_lock.release()

    __enter__ = acquire

    def __exit__(self, t, v, tb):
        self.release()

    def _get_greenlet_lock(self):
        if not hasattr(self._thread_local, 'greenlet_lock'):
            greenlet_lock = self._thread_local.greenlet_lock = Semaphore(1)
        else:
            greenlet_lock = self._thread_local.greenlet_lock
        return greenlet_lock

    def _is_owned(self):
        return self._owner == (get_ident(), id(getcurrent()))
