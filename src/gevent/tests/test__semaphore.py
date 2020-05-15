###
# This file is test__semaphore.py only for organization purposes.
# The public API,
# and the *only* correct place to import Semaphore --- even in tests ---
# is ``gevent.lock``, never ``gevent._semaphore``.
##
from __future__ import print_function
from __future__ import absolute_import

import weakref

import gevent
import gevent.exceptions
from gevent.lock import Semaphore

import gevent.testing as greentest


class TestSemaphore(greentest.TestCase):

    # issue 39
    def test_acquire_returns_false_after_timeout(self):
        s = Semaphore(value=0)
        result = s.acquire(timeout=0.01)
        assert result is False, repr(result)

    def test_release_twice(self):
        s = Semaphore()
        result = []
        s.rawlink(lambda s: result.append('a'))
        s.release()
        s.rawlink(lambda s: result.append('b'))
        s.release()
        gevent.sleep(0.001)
        # The order, though, is not guaranteed.
        self.assertEqual(sorted(result), ['a', 'b'])

    def test_semaphore_weakref(self):
        s = Semaphore()
        r = weakref.ref(s)
        self.assertEqual(s, r())

    @greentest.ignores_leakcheck
    def test_semaphore_in_class_with_del(self):
        # Issue #704. This used to crash the process
        # under PyPy through at least 4.0.1 if the Semaphore
        # was implemented with Cython.
        class X(object):
            def __init__(self):
                self.s = Semaphore()

            def __del__(self):
                self.s.acquire()

        X()
        import gc
        gc.collect()
        gc.collect()


    def test_rawlink_on_unacquired_runs_notifiers(self):
        # https://github.com/gevent/gevent/issues/1287

        # Rawlinking a ready semaphore should fire immediately,
        # not raise LoopExit
        s = Semaphore()
        gevent.wait([s])


class TestAcquireContended(greentest.TestCase):
    # Tests that the object can be acquired correctly across
    # multiple threads.
    # Used as a base class.

    # See https://github.com/gevent/gevent/issues/1437

    def _makeOne(self):
        # Create an object that is associated with the current hub. If
        # we don't do this now, it gets initialized lazily the first
        # time it would have to block, which, in the event of threads,
        # would be from an arbitrary thread.
        return Semaphore(1, gevent.get_hub())


    def test_acquire_in_one_then_another(self):
        from gevent import monkey
        self.assertFalse(monkey.is_module_patched('threading'))
        import sys
        import threading

        sem = self._makeOne()
        # Make future acquires block
        print("acquiring", sem)
        sem.acquire()

        exc_info = []

        def thread_main():
            # XXX: When this is fixed, this will have to be modified
            # to avoid deadlock, but being careful to still test
            # the initial conditions (e.g., that this doesn't throw;
            # we can't pass block=False because that bypasses the part
            # that would throw.)
            try:
                sem.acquire()
            except:
                exc_info[:] = sys.exc_info()

        t = threading.Thread(target=thread_main)
        t.start()
        t.join()

        try:
            self.assertEqual(exc_info, [])
        finally:
            exc_info = None

@greentest.skipOnPurePython("Needs C extension")
class TestCExt(greentest.TestCase):

    def test_c_extension(self):
        self.assertEqual(Semaphore.__module__,
                         'gevent._gevent_c_semaphore')


class SwitchWithFixedHash(object):
    # Replaces greenlet.switch with a callable object
    # with a hash code we control. This only matters if
    # we're hashing this somewhere (which we used to), but
    # that doesn't preserve order, so we don't do
    # that anymore.

    def __init__(self, greenlet, hashcode):
        self.switch = greenlet.switch
        self.hashcode = hashcode

    def __hash__(self):
        raise AssertionError

    def __eq__(self, other):
        raise AssertionError

    def __call__(self, *args, **kwargs):
        return self.switch(*args, **kwargs)

    def __repr__(self):
        return repr(self.switch)

class FirstG(gevent.Greenlet):
    # A greenlet whose switch method will have a low hashcode.

    hashcode = 10

    def __init__(self, *args, **kwargs):
        gevent.Greenlet.__init__(self, *args, **kwargs)
        self.switch = SwitchWithFixedHash(self, self.hashcode)


class LastG(FirstG):
    # A greenlet whose switch method will have a high hashcode.
    hashcode = 12


def acquire_then_exit(sem, should_quit):
    sem.acquire()
    should_quit.append(True)


def acquire_then_spawn(sem, should_quit):
    if should_quit:
        return
    sem.acquire()
    g = FirstG.spawn(release_then_spawn, sem, should_quit)
    g.join()

def release_then_spawn(sem, should_quit):
    sem.release()
    if should_quit: # pragma: no cover
        return
    g = FirstG.spawn(acquire_then_spawn, sem, should_quit)
    g.join()

class TestSemaphoreFair(greentest.TestCase):

    @greentest.ignores_leakcheck
    def test_fair_or_hangs(self):
        # If the lock isn't fair, this hangs, spinning between
        # the last two greenlets.
        # See https://github.com/gevent/gevent/issues/1487
        sem = Semaphore()
        should_quit = []

        keep_going1 = FirstG.spawn(acquire_then_spawn, sem, should_quit)
        keep_going2 = FirstG.spawn(acquire_then_spawn, sem, should_quit)
        exiting = LastG.spawn(acquire_then_exit, sem, should_quit)

        with self.assertRaises(gevent.exceptions.LoopExit):
            gevent.joinall([keep_going1, keep_going2, exiting])

        self.assertTrue(exiting.dead, exiting)
        self.assertTrue(keep_going2.dead, keep_going2)
        self.assertFalse(keep_going1.dead, keep_going1)


if __name__ == '__main__':
    greentest.main()
