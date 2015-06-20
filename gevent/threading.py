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
    __threading__._active.pop(id(g))


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

if PYPY:
    # Make sure the MainThread can be found by our current greenlet ID,
    # otherwise we get a new DummyThread, which cannot be joined.
    # Fixes tests in test_threading_2
    if _get_ident() not in __threading__._active and len(__threading__._active) == 1:
        k, v = __threading__._active.items()[0]
        del __threading__._active[k]
        __threading__._active[_get_ident()] = v

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

if sys.version_info[:2] >= (3, 3):
    __implements__.remove('_get_ident')
    __implements__.append('get_ident')
    get_ident = _get_ident
    __implements__.remove('_sleep')
