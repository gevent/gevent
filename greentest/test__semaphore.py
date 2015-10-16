import greentest
import gevent
from gevent.lock import Semaphore
from gevent.thread import allocate_lock
import weakref
try:
    from _thread import allocate_lock as std_allocate_lock
except ImportError: # Py2
    from thread import allocate_lock as std_allocate_lock


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
        self.assertEqual(result, ['a', 'b'])

    def test_semaphore_weakref(self):
        s = Semaphore()
        r = weakref.ref(s)
        self.assertEqual(s, r())


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
        self.assertTrue(isinstance(g_exc, type(std_exc)), (g_exc, std_exc))


if __name__ == '__main__':
    greentest.main()
