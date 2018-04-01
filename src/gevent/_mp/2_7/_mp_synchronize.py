from multiprocessing.synchronize import SemLock as _SemLock, \
    Semaphore as _Semaphore, \
    BoundedSemaphore as _BoundedSemaphore, \
    Lock as _Lock, \
    RLock as _RLock

from gevent.hub import _get_hub_noargs as get_hub

__implements__ = ["SemLock", "Semaphore", "BoundedSemaphore", "Lock", "RLock"]
__target__ = "multiprocessing.synchronize"


class SemLock(_SemLock):
    def _make_methods(self):
        self._acquire = self._semlock.acquire
        self._release = self._semlock.release

    def acquire(self, *args, **kwargs):
        return get_hub().threadpool.apply(self._acquire)

    def release(self, *args, **kwargs):
        self._release()

    def __enter__(self):
        return get_hub().threadpool.apply(super(SemLock, self).__enter__)


Semaphore = type("Semaphore", (SemLock,), dict(_Semaphore.__dict__))
BoundedSemaphore = type("BoundedSemaphore", (Semaphore,), dict(_BoundedSemaphore.__dict__))
Lock = type("Lock", (SemLock,), dict(_Lock.__dict__))
RLock = type("RLock", (SemLock,), dict(_RLock.__dict__))
