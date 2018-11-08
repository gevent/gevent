import gevent.testing as greentest
import gevent
from gevent.lock import Semaphore
from gevent.thread import allocate_lock
import weakref
try:
    from _thread import allocate_lock as std_allocate_lock
except ImportError: # Py2
    from thread import allocate_lock as std_allocate_lock

# pylint:disable=broad-except

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

    test_semaphore_in_class_with_del.ignore_leakcheck = True

    def test_rawlink_on_unacquired_runs_notifiers(self):
        # https://github.com/gevent/gevent/issues/1287

        # Rawlinking a ready semaphore should fire immediately,
        # not raise LoopExit
        s = Semaphore()
        gevent.wait([s])

class TestLock(greentest.TestCase):

    def test_release_unheld_lock(self):
        std_lock = std_allocate_lock()
        g_lock = allocate_lock()
        try:
            std_lock.release()
            self.fail("Should have thrown an exception")
        except Exception as e:
            std_exc = e

        try:
            g_lock.release()
            self.fail("Should have thrown an exception")
        except Exception as e:
            g_exc = e
        self.assertIsInstance(g_exc, type(std_exc))


@greentest.skipOnPurePython("Needs C extension")
class TestCExt(greentest.TestCase):

    def test_c_extension(self):
        self.assertEqual(Semaphore.__module__,
                         'gevent.__semaphore')


if __name__ == '__main__':
    greentest.main()
