from __future__ import absolute_import


__implements__ = ['local',
                  '_start_new_thread',
                  '_allocate_lock',
                  'Lock',
                  '_get_ident',
                  '_sleep',
                  '_DummyThread']


import threading as __threading__
_DummyThread_ = __threading__._DummyThread
from gevent.local import local
from gevent.thread import start_new_thread as _start_new_thread, allocate_lock as _allocate_lock, get_ident as _get_ident
from gevent.hub import sleep as _sleep, getcurrent, PYPY
Lock = _allocate_lock


def _cleanup(g):
    __threading__._active.pop(id(g), None)


class _DummyThread(_DummyThread_):
    # instances of this will cleanup its own entry
    # in ``threading._active``

    def __init__(self):
        _DummyThread_.__init__(self)
        g = getcurrent()
        rawlink = getattr(g, 'rawlink', None)
        if rawlink is not None:
            rawlink(_cleanup)

    def _Thread__stop(self):
        pass

# Make sure the MainThread can be found by our current greenlet ID,
# otherwise we get a new DummyThread, which cannot be joined.
# Fixes tests in test_threading_2 under PyPy, and generally makes things nicer
# when gevent.threading is imported before monkey patching or not at all
# XXX: This assumes that the import is happening in the "main" greenlet
if _get_ident() not in __threading__._active and len(__threading__._active) == 1:
    k, v = next(iter(__threading__._active.items()))
    del __threading__._active[k]
    v._Thread__ident = _get_ident()
    __threading__._active[_get_ident()] = v
    del k
    del v

    # Avoid printing an error on shutdown trying to remove the thread entry
    # we just replaced if we're not fully monkey patched in
    # XXX: This causes a hang on PyPy for some unknown reason (as soon as class _active
    # defines __delitem__, shutdown hangs. Maybe due to something with the GC?)
    if not PYPY:
        _MAIN_THREAD = __threading__._get_ident() if hasattr(__threading__, '_get_ident') else __threading__.get_ident()

        class _active(dict):
            def __delitem__(self, k):
                if k == _MAIN_THREAD and k not in self:
                    return
                dict.__delitem__(self, k)

        __threading__._active = _active(__threading__._active)


import sys
if sys.version_info[:2] >= (3, 4):
    # XXX: Issue 18808 breaks us on Python 3.4.
    # Thread objects now expect a callback from the interpreter itself
    # (threadmodule.c:release_sentinel). Because this never happens
    # when a greenlet exits, join() and friends will block forever.
    # The solution below involves capturing the greenlet when it is
    # started and deferring the known broken methods to it.

    class Thread(__threading__.Thread):
        _greenlet = None

        def is_alive(self):
            return bool(self._greenlet)

        isAlive = is_alive

        def _set_tstate_lock(self):
            self._greenlet = getcurrent()

        def run(self):
            try:
                super(Thread, self).run()
            finally:
                # avoid ref cycles, but keep in __dict__ so we can
                # distinguish the started/never-started case
                self._greenlet = None
                self._stop() # mark as finished

        def join(self, timeout=None):
            if '_greenlet' not in self.__dict__:
                raise RuntimeError("Cannot join an inactive thread")
            if self._greenlet is None:
                return
            self._greenlet.join(timeout=timeout)

        def _wait_for_tstate_lock(self, *args, **kwargs):
            raise NotImplementedError()

    __implements__.append('Thread')

    # The main thread is patched up with more care in monkey.py
    #t = __threading__.current_thread()
    #if isinstance(t, __threading__.Thread):
    #    t.__class__ = Thread
    #    t._greenlet = getcurrent()

if sys.version_info[:2] >= (3, 3):
    __implements__.remove('_get_ident')
    __implements__.append('get_ident')
    get_ident = _get_ident
    __implements__.remove('_sleep')

    # Python 3 changed the implementation of threading.RLock
    # Previously it was a factory function around threading._RLock
    # which in turn used _allocate_lock. Now, it wants to use
    # threading._CRLock, which is imported from _thread.RLock and as such
    # is implemented in C. So it bypasses our _allocate_lock function.
    # Fortunately they left the Python fallback in place
    assert hasattr(__threading__, '_CRLock'), "Unsupported Python version"
    _CRLock = None
    __implements__.append('_CRLock')
