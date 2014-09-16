import sys
import random
import gevent
from gevent.lock import NativeFriendlyRLock
import threading
import lock_tests

try:
    from test import support
except ImportError:
    from test import test_support as support


class NativeFriendlyRLockTestCase(lock_tests.RLockTests):
    locktype = staticmethod(NativeFriendlyRLock)

    def setUp(self):
        super(NativeFriendlyRLockTestCase, self).setUp()
        sys.setcheckinterval(100)

    def test_acquire_release(self):
        l = self.locktype()
        l.acquire()
        l.release()

    def test_double_acquire_double_release(self):
        l = self.locktype()
        l.acquire()
        l.acquire()
        l.release()
        l.release()

    def test_release_too_much(self):
        l = self.locktype()
        self.assertRaises(RuntimeError, l.release)
        l.acquire()
        l.release()
        self.assertRaises(RuntimeError, l.release)

    def test_acquire_release__two_threads(self):
        l = self.locktype()

        def foo(lock):
            lock.acquire()
            lock.release()

        a = threading.Thread(target=foo, args=(l,))
        b = threading.Thread(target=foo, args=(l,))
        a.start()
        b.start()
        a.join()
        b.join()

    def test_lock_sharing_blocking(self):
        def greenlet_func(lock, n_threads, thread_idx, n_greenlets, greenlet_idx, l):
            with lock:
                l.append(thread_idx * n_greenlets + greenlet_idx)

        def thread_func(lock, n_threads, thread_idx, n_greenlets, l):
            greenlets = []
            for i in range(n_greenlets):
                greenlets.append(gevent.spawn(greenlet_func, lock, n_threads, thread_idx, n_greenlets, i, l))
            gevent.joinall(greenlets)

        n_threads = 10
        n_greenlets = 20
        threads = []
        lock = self.locktype()
        result = []
        for i in range(n_threads):
            threads.append(threading.Thread(target=thread_func, args=(lock, n_threads, i, n_greenlets, result)))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.assertEquals(list(range(n_threads * n_greenlets)), sorted(result))

    def test_lock_sharing_between_greenlets(self):
        def greenlet_func(l):
            for i in range(5):
                l.append(i)
                gevent.sleep(0.01)

        def greenlet_lock_func(lock):
            lock.acquire()

    def test_fair_acquire_between_threads(self):
        random.seed(1)

        def thread_func(lock, acquire_array, lock_array, index):
            gevent.sleep(random.uniform(0, 0.1))
            # We use the fact that the GIL prevents CPython from context switching between the acquire_array.append()
            # and the lock.acquire() when we set the check interval to a great value
            sys.setcheckinterval(10000000)
            acquire_array.append(index)
            with lock:
                sys.setcheckinterval(1)
                lock_array.append(index)

        lock = self.locktype()
        acquire_array = []
        lock_array = []
        n_threads = 30
        threads = [threading.Thread(target=thread_func, args=(lock, acquire_array, lock_array, i))
                   for i in range(n_threads)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEquals(n_threads, len(acquire_array))
        self.assertEquals(list(range(n_threads)), sorted(acquire_array))
        self.assertEquals(acquire_array, lock_array)

    def test_fair_acquire_between_threads_and_greenlets(self):
        random.seed(1)

        def greenlet_func(lock, acquire_array, lock_array, n):
            gevent.sleep(random.uniform(0, 0.1))
            # We use the fact that the GIL prevents CPython from context switching between the acquire_array.append()
            # and the lock.acquire() when we set the check interval to a great value
            sys.setcheckinterval(10000000)
            acquire_array.append(n)
            with lock:
                sys.setcheckinterval(1)
                lock_array.append(n)

        def thread_func(lock, acquire_array, lock_array, n_greenlets, index):
            gevent.sleep(random.uniform(0, 0.1))
            greenlets = [gevent.spawn(greenlet_func, lock, acquire_array, lock_array, n_greenlets * index + i)
                         for i in range(n_greenlets)]
            gevent.joinall(greenlets)

        lock = self.locktype()
        acquire_array = []
        lock_array = []
        n_threads = 20
        n_greenlets = 20
        threads = [threading.Thread(target=thread_func, args=(lock, acquire_array, lock_array, n_greenlets, i))
                   for i in range(n_threads)]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEquals(n_threads * n_greenlets, len(acquire_array))
        self.assertEquals(list(range(n_threads * n_greenlets)), sorted(acquire_array))
        self.assertEquals(list(range(n_threads * n_greenlets)), sorted(lock_array))
        self.maxDiff = None
        self.assertEquals(acquire_array, lock_array)


def main():
    support.run_unittest(NativeFriendlyRLockTestCase)

if __name__ == "__main__":
    main()
