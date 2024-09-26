# -*- coding: utf-8 -*-
"""
The implementation of thread patching for Python versions
prior to 3.13.

Internal use only.
"""
import sys

from ._util import _patch_module
from ._util import _queue_warning
from ._util import _notify_patch

from ._state import is_object_patched

def _patch_existing_locks(threading):
    if len(list(threading.enumerate())) != 1:
        return
    # This is used to protect internal data structures for enumerate.
    # It's acquired when threads are started and when they're stopped.
    # Stopping a thread checks a Condition, which on Python 2 wants to test
    # _is_owned of its (patched) Lock. Since our LockType doesn't have
    # _is_owned, it tries to acquire the lock non-blocking; that triggers a
    # switch. If the next thing in the callback list was a thread that needed
    # to start or end, we wouldn't be able to acquire this native lock
    # because it was being held already; we couldn't switch either, so we'd
    # block permanently.
    threading._active_limbo_lock = threading._allocate_lock()
    try:
        tid = threading.get_ident()
    except AttributeError:
        tid = threading._get_ident()
    rlock_type = type(threading.RLock())
    try:
        import importlib._bootstrap
    except ImportError:
        class _ModuleLock(object):
            pass
    else:
        _ModuleLock = importlib._bootstrap._ModuleLock # python 2 pylint: disable=no-member
    # It might be possible to walk up all the existing stack frames to find
    # locked objects...at least if they use `with`. To be sure, we look at every object
    # Since we're supposed to be done very early in the process, there shouldn't be
    # too many.

    # Note that the C implementation of locks, at least on some
    # versions of CPython, cannot be found and cannot be fixed (they simply
    # don't show up to GC; see https://github.com/gevent/gevent/issues/1354)

    # By definition there's only one thread running, so the various
    # owner attributes were the old (native) thread id. Make it our
    # current greenlet id so that when it wants to unlock and compare
    # self.__owner with _get_ident(), they match.
    gc = __import__('gc')
    for o in gc.get_objects():
        if isinstance(o, rlock_type):
            for owner_name in (
                    '_owner', # Python 3 or backported PyPy2
                    '_RLock__owner', # Python 2
            ):
                if hasattr(o, owner_name):
                    if getattr(o, owner_name) is not None:
                        setattr(o, owner_name, tid)
                    break
            else: # pragma: no cover
                raise AssertionError(
                    "Unsupported Python implementation; "
                    "Found unknown lock implementation.",
                    vars(o)
                )
        elif isinstance(o, _ModuleLock):
            if o.owner is not None:
                o.owner = tid


def patch(threading=True, _threading_local=True, Event=True, logging=True,
          existing_locks=True,
          _warnings=None):
    # XXX: Simplify
    # pylint:disable=too-many-branches,too-many-locals,too-many-statements

    # Description of the hang:
    # There is an incompatibility with patching 'thread' and the 'multiprocessing' module:
    # The problem is that multiprocessing.queues.Queue uses a half-duplex multiprocessing.Pipe,
    # which is implemented with os.pipe() and _multiprocessing.Connection. os.pipe isn't patched
    # by gevent, as it returns just a fileno. _multiprocessing.Connection is an internal implementation
    # class implemented in C, which exposes a 'poll(timeout)' method; under the covers, this issues a
    # (blocking) select() call: hence the need for a real thread. Except for that method, we could
    # almost replace Connection with gevent.fileobject.SocketAdapter, plus a trivial
    # patch to os.pipe (below). Sigh, so close. (With a little work, we could replicate that method)

    # import os
    # import fcntl
    # os_pipe = os.pipe
    # def _pipe():
    #   r, w = os_pipe()
    #   fcntl.fcntl(r, fcntl.F_SETFL, os.O_NONBLOCK)
    #   fcntl.fcntl(w, fcntl.F_SETFL, os.O_NONBLOCK)
    #   return r, w
    # os.pipe = _pipe

    # The 'threading' module copies some attributes from the
    # thread module the first time it is imported. If we patch 'thread'
    # before that happens, then we store the wrong values in 'saved',
    # So if we're going to patch threading, we either need to import it
    # before we patch thread, or manually clean up the attributes that
    # are in trouble. The latter is tricky because of the different names
    # on different versions.

    from .api import patch_item

    gevent_threading_mod = None
    if threading:
        threading_mod = __import__('threading')
        # Capture the *real* current thread object before
        # we start returning DummyThread objects, for comparison
        # to the main thread.
        orig_current_thread = threading_mod.current_thread()
    else:
        threading_mod = None
        orig_current_thread = None

    gevent_thread_mod, thread_mod = _patch_module('thread',
                                                  _warnings=_warnings,
                                                  _notify_did_subscribers=False)


    if threading:
        gevent_threading_mod, _ = _patch_module('threading',
                                                _warnings=_warnings,
                                                _notify_did_subscribers=False)

        if Event:
            from gevent.event import Event
            patch_item(threading_mod, 'Event', Event)
            # Python 2 had `Event` as a function returning
            # the private class `_Event`. Some code may be relying
            # on that.
            if hasattr(threading_mod, '_Event'):
                patch_item(threading_mod, '_Event', Event)

        if existing_locks:
            _patch_existing_locks(threading_mod)

        if logging and 'logging' in sys.modules:
            logging = __import__('logging')
            patch_item(logging, '_lock', threading_mod.RLock())
            for wr in logging._handlerList:
                # In py26, these are actual handlers, not weakrefs
                handler = wr() if callable(wr) else wr
                if handler is None:
                    continue
                if not hasattr(handler, 'lock'):
                    raise TypeError("Unknown/unsupported handler %r" % handler)
                handler.lock = threading_mod.RLock()

    if _threading_local:
        _threading_local = __import__('_threading_local')
        from gevent.local import local
        patch_item(_threading_local, 'local', local)

    def make_join_func(thread, thread_greenlet):
        from gevent.hub import sleep
        from time import time

        def join(timeout=None):
            end = None
            if threading_mod.current_thread() is thread:
                raise RuntimeError("Cannot join current thread")
            if thread_greenlet is not None and thread_greenlet.dead:
                return
            # You may ask: Why not call thread_greenlet.join()?
            # Well, in the one case we actually have a greenlet, it's the
            # low-level greenlet.greenlet object for the main thread, which
            # doesn't have a join method.
            #
            # You may ask: Why not become the main greenlet's *parent*
            # so you can get notified when it finishes? Because you can't
            # create a greenlet cycle (the current greenlet is a descendent
            # of the parent), and nor can you set a greenlet's parent to None,
            # so there can only ever be one greenlet with a parent of None: the main
            # greenlet, the one we need to watch.
            #
            # You may ask: why not swizzle out the problematic lock on the main thread
            # into a gevent friendly lock? Well, the interpreter actually depends on that
            # for the main thread in threading._shutdown; see below.

            if not thread.is_alive():
                return

            if timeout:
                end = time() + timeout

            while thread.is_alive():
                if end is not None and time() > end:
                    return
                sleep(0.01)
        return join

    if threading:
        from gevent.threading import main_native_thread

        for thread in threading_mod._active.values():
            if thread == main_native_thread():
                continue
            thread.join = make_join_func(thread, None)

    # Issue 18808 changes the nature of Thread.join() to use
    # locks. This means that a greenlet spawned in the main thread
    # (which is already running) cannot wait for the main thread---it
    # hangs forever. We patch around this if possible. See also
    # gevent.threading.
    greenlet = __import__('greenlet')
    already_patched = is_object_patched('threading', '_shutdown')
    orig_shutdown = threading_mod._shutdown

    if orig_current_thread == threading_mod.main_thread() and not already_patched:
        main_thread = threading_mod.main_thread()
        _greenlet = main_thread._greenlet = greenlet.getcurrent()
        # XXX: Changed for 3.13. No longer uses this, uses a 'handle'
        #
        try:
            main_thread.__real_tstate_lock = main_thread._tstate_lock
        except AttributeError:
            pass
        else:
            assert main_thread.__real_tstate_lock is not None
            # The interpreter will call threading._shutdown
            # when the main thread exits and is about to
            # go away. It is called *in* the main thread. This
            # is a perfect place to notify other greenlets that
            # the main thread is done. We do this by overriding the
            # lock of the main thread during operation, and only restoring
            # it to the native blocking version at shutdown time
            # (the interpreter also has a reference to this lock in a
            # C data structure).
            main_thread._tstate_lock = threading_mod.Lock()
            main_thread._tstate_lock.acquire()

        def _shutdown():
            # Release anyone trying to join() me,
            # and let us switch to them.
            if not main_thread._tstate_lock:
                return

            main_thread._tstate_lock.release()
            from gevent import sleep
            try:
                sleep()
            except: # pylint:disable=bare-except
                # A greenlet could have .kill() us
                # or .throw() to us. I'm the main greenlet,
                # there's no where else for this to go.
                from gevent  import get_hub
                get_hub().print_exception(_greenlet, *sys.exc_info())

            # Now, this may have resulted in us getting stopped
            # if some other greenlet actually just ran there.
            # That's not good, we're not supposed to be stopped
            # when we enter _shutdown.
            main_thread._is_stopped = False
            main_thread._tstate_lock = main_thread.__real_tstate_lock
            main_thread.__real_tstate_lock = None
            # The only truly blocking native shutdown lock to
            # acquire should be our own (hopefully), and the call to
            # _stop that orig_shutdown makes will discard it.

            orig_shutdown()
            patch_item(threading_mod, '_shutdown', orig_shutdown)

        patch_item(threading_mod, '_shutdown', _shutdown)

        # We create a bit of a reference cycle here,
        # so main_thread doesn't get to be collected in a timely way.
        # Not good. Take it out of dangling so we don't get
        # warned about it.
        threading_mod._dangling.remove(main_thread)

        # Patch up the ident of the main thread to match. This
        # matters if threading was imported before monkey-patching
        # thread
        oldid = main_thread.ident
        main_thread._ident = threading_mod.get_ident()
        if oldid in threading_mod._active:
            threading_mod._active[main_thread.ident] = threading_mod._active[oldid]
        if oldid != main_thread.ident:
            del threading_mod._active[oldid]
    elif not already_patched:
        _queue_warning("Monkey-patching not on the main thread; "
                       "threading.main_thread().join() will hang from a greenlet",
                       _warnings)

        main_thread = threading_mod.main_thread()
        def _shutdown():
            # We've patched get_ident but *did not* patch the
            # main_thread.ident value. Beginning in Python 3.9.8
            # and then later releases (3.10.1, probably), the
            # _main_thread object is only _stop() if the ident of
            # the current thread (the *real* main thread) matches
            # the ident of the _main_thread object. But without doing that,
            # the main thread's shutdown lock (threading._shutdown_locks) is never
            # removed *or released*, thus hanging the interpreter.
            # XXX: There's probably a better way to do this. Probably need to take a
            # step back and look at the whole picture.
            main_thread._ident = threading_mod.get_ident()
            orig_shutdown()
            patch_item(threading_mod, '_shutdown', orig_shutdown)
        patch_item(threading_mod, '_shutdown', _shutdown)

    from gevent import events
    _notify_patch(events.GeventDidPatchModuleEvent('thread', gevent_thread_mod, thread_mod))
    if gevent_threading_mod is not None:
        _notify_patch(events.GeventDidPatchModuleEvent('threading', gevent_threading_mod, threading_mod))
