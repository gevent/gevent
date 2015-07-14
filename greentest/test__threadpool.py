import sys
from time import time, sleep
import random
import weakref
import greentest
from gevent.threadpool import ThreadPool
import gevent
from greentest import ExpectedException
import six
import gc


PYPY = hasattr(sys, 'pypy_version_info')


class TestCase(greentest.TestCase):

    def cleanup(self):
        pool = getattr(self, 'pool', None)
        if pool is not None:
            pool.kill()
            del self.pool


class PoolBasicTests(TestCase):

    def test_execute_async(self):
        self.pool = pool = ThreadPool(2)
        r = []
        first = pool.spawn(r.append, 1)
        first.get()
        self.assertEqual(r, [1])
        gevent.sleep(0)

        pool.apply_async(r.append, (2, ))
        self.assertEqual(r, [1])

        pool.apply_async(r.append, (3, ))
        self.assertEqual(r, [1])

        pool.apply_async(r.append, (4, ))
        self.assertEqual(r, [1])
        gevent.sleep(0.01)
        self.assertEqual(sorted(r), [1, 2, 3, 4])

    def test_apply(self):
        self.pool = pool = ThreadPool(1)
        result = pool.apply(lambda a: ('foo', a), (1, ))
        self.assertEqual(result, ('foo', 1))

    def test_apply_raises(self):
        self.pool = pool = ThreadPool(1)

        def raiser():
            raise ExpectedException()

        try:
            pool.apply(raiser)
        except ExpectedException:
            pass
        else:
            self.fail("Should have raised ExpectedException")
    # Don't let the metaclass automatically force any error
    # that reaches the hub from a spawned greenlet to become
    # fatal; that defeats the point of the test.
    test_apply_raises.error_fatal = False

    def test_init_valueerror(self):
        self.switch_expected = False
        self.assertRaises(ValueError, ThreadPool, -1)
        self.pool = None

#
# tests from standard library test/test_multiprocessing.py


class TimingWrapper(object):

    def __init__(self, func):
        self.func = func
        self.elapsed = None

    def __call__(self, *args, **kwds):
        t = time()
        try:
            return self.func(*args, **kwds)
        finally:
            self.elapsed = time() - t


def sqr(x, wait=0.0):
    sleep(wait)
    return x * x


def sqr_random_sleep(x):
    sleep(random.random() * 0.1)
    return x * x


TIMEOUT1, TIMEOUT2, TIMEOUT3 = 0.082, 0.035, 0.14


class TestPool(TestCase):
    __timeout__ = 5
    size = 1

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.pool = ThreadPool(self.size)

    def test_apply(self):
        papply = self.pool.apply
        self.assertEqual(papply(sqr, (5,)), sqr(5))
        self.assertEqual(papply(sqr, (), {'x': 3}), sqr(x=3))

    def test_map(self):
        pmap = self.pool.map
        self.assertEqual(pmap(sqr, range(10)), list(map(sqr, range(10))))
        self.assertEqual(pmap(sqr, range(100)), list(map(sqr, range(100))))

    def test_async(self):
        res = self.pool.apply_async(sqr, (7, TIMEOUT1,))
        get = TimingWrapper(res.get)
        self.assertEqual(get(), 49)
        self.assertAlmostEqual(get.elapsed, TIMEOUT1, 1)

    def test_async_callback(self):
        result = []
        res = self.pool.apply_async(sqr, (7, TIMEOUT1,), callback=lambda x: result.append(x))
        get = TimingWrapper(res.get)
        self.assertEqual(get(), 49)
        self.assertAlmostEqual(get.elapsed, TIMEOUT1, 1)
        gevent.sleep(0)  # let's the callback run
        assert result == [49], result

    def test_async_timeout(self):
        res = self.pool.apply_async(sqr, (6, TIMEOUT2 + 0.2))
        get = TimingWrapper(res.get)
        self.assertRaises(gevent.Timeout, get, timeout=TIMEOUT2)
        self.assertAlmostEqual(get.elapsed, TIMEOUT2, 1)
        self.pool.join()

    def test_imap(self):
        it = self.pool.imap(sqr, range(10))
        self.assertEqual(list(it), list(map(sqr, range(10))))

        it = self.pool.imap(sqr, range(10))
        for i in range(10):
            self.assertEqual(six.advance_iterator(it), i * i)
        self.assertRaises(StopIteration, lambda: six.advance_iterator(it))

        it = self.pool.imap(sqr, range(1000))
        for i in range(1000):
            self.assertEqual(six.advance_iterator(it), i * i)
        self.assertRaises(StopIteration, lambda: six.advance_iterator(it))

    def test_imap_gc(self):
        it = self.pool.imap(sqr, range(10))
        for i in range(10):
            self.assertEqual(six.advance_iterator(it), i * i)
            gc.collect()
        self.assertRaises(StopIteration, lambda: six.advance_iterator(it))

    def test_imap_unordered_gc(self):
        it = self.pool.imap_unordered(sqr, range(10))
        result = []
        for i in range(10):
            result.append(six.advance_iterator(it))
            gc.collect()
        self.assertRaises(StopIteration, lambda: six.advance_iterator(it))
        self.assertEqual(sorted(result), [x * x for x in range(10)])

    def test_imap_random(self):
        it = self.pool.imap(sqr_random_sleep, range(10))
        self.assertEqual(list(it), list(map(sqr, range(10))))

    def test_imap_unordered(self):
        it = self.pool.imap_unordered(sqr, range(1000))
        self.assertEqual(sorted(it), list(map(sqr, range(1000))))

        it = self.pool.imap_unordered(sqr, range(1000))
        self.assertEqual(sorted(it), list(map(sqr, range(1000))))

    def test_imap_unordered_random(self):
        it = self.pool.imap_unordered(sqr_random_sleep, range(10))
        self.assertEqual(sorted(it), list(map(sqr, range(10))))

    def test_terminate(self):
        size = self.size or 10
        result = self.pool.map_async(sleep, [0.1] * (size * 2))
        gevent.sleep(0.1)
        kill = TimingWrapper(self.pool.kill)
        kill()
        assert kill.elapsed < 0.1 * self.size + 0.5, kill.elapsed
        result.join()

    def sleep(self, x):
        sleep(float(x) / 10.)
        return str(x)

    def test_imap_unordered_sleep(self):
        # testing that imap_unordered returns items in competion order
        result = list(self.pool.imap_unordered(self.sleep, [10, 1, 2]))
        if self.pool.size == 1:
            expected = ['10', '1', '2']
        else:
            expected = ['1', '2', '10']
        self.assertEqual(result, expected)


class TestPool2(TestPool):
    size = 2

    def test_recursive_apply(self):
        p = self.pool

        def a():
            return p.apply(b)

        def b():
            # make sure we can do both types of callbacks
            # (loop iteration and end-of-loop) in the recursive
            # call
            gevent.sleep()
            gevent.sleep(0.001)
            return "B"

        result = p.apply(a)
        self.assertEqual(result, "B")
    # Asking for the hub in the new thread shows up as a "leak"
    test_recursive_apply.ignore_leakcheck = True


class TestPool3(TestPool):
    size = 3


class TestPool10(TestPool):
    size = 10
    __timeout__ = 5


# class TestJoinSleep(greentest.GenericGetTestCase):
#
#     def wait(self, timeout):
#         pool = ThreadPool(1)
#         pool.spawn(gevent.sleep, 10)
#         pool.join(timeout=timeout)
#
#
# class TestJoinSleep_raise_error(greentest.GenericWaitTestCase):
#
#     def wait(self, timeout):
#         pool = ThreadPool(1)
#         g = pool.spawn(gevent.sleep, 10)
#         pool.join(timeout=timeout, raise_error=True)


class TestJoinEmpty(TestCase):
    switch_expected = False

    def test(self):
        self.pool = ThreadPool(1)
        self.pool.join()


class TestSpawn(TestCase):
    switch_expected = True

    def test(self):
        self.pool = pool = ThreadPool(1)
        self.assertEqual(len(pool), 0)
        log = []
        sleep_n_log = lambda item, seconds: [sleep(seconds), log.append(item)]
        pool.spawn(sleep_n_log, 'a', 0.1)
        self.assertEqual(len(pool), 1)
        pool.spawn(sleep_n_log, 'b', 0.1)
        # even though the pool is of size 1, it can contain 2 items
        # since we allow +1 for better throughput
        self.assertEqual(len(pool), 2)
        gevent.sleep(0.15)
        self.assertEqual(log, ['a'])
        self.assertEqual(len(pool), 1)
        gevent.sleep(0.15)
        self.assertEqual(log, ['a', 'b'])
        self.assertEqual(len(pool), 0)


def error_iter():
    yield 1
    yield 2
    raise greentest.ExpectedException


class TestErrorInIterator(TestCase):

    error_fatal = False

    def test(self):
        self.pool = ThreadPool(3)
        self.assertRaises(greentest.ExpectedException, self.pool.map, lambda x: None, error_iter())
        gevent.sleep(0.001)

    def test_unordered(self):
        self.pool = ThreadPool(3)

        def unordered():
            return list(self.pool.imap_unordered(lambda x: None, error_iter()))

        self.assertRaises(greentest.ExpectedException, unordered)
        gevent.sleep(0.001)


class TestMaxsize(TestCase):

    def test_inc(self):
        self.pool = ThreadPool(0)
        done = []
        gevent.spawn(self.pool.spawn, done.append, 1)
        gevent.spawn_later(0.0001, self.pool.spawn, done.append, 2)
        gevent.sleep(0.01)
        self.assertEqual(done, [])
        self.pool.maxsize = 1
        gevent.sleep(0.01)
        self.assertEqual(done, [1, 2])

    def test_setzero(self):
        pool = self.pool = ThreadPool(3)
        pool.spawn(sleep, 0.1)
        pool.spawn(sleep, 0.2)
        pool.spawn(sleep, 0.3)
        gevent.sleep(0.2)
        self.assertEqual(pool.size, 3)
        pool.maxsize = 0
        gevent.sleep(0.2)
        self.assertEqual(pool.size, 0)


class TestSize(TestCase):

    def test(self):
        pool = self.pool = ThreadPool(2)
        self.assertEqual(pool.size, 0)
        pool.size = 1
        self.assertEqual(pool.size, 1)
        pool.size = 2
        self.assertEqual(pool.size, 2)
        pool.size = 1
        self.assertEqual(pool.size, 1)

        def set_neg():
            pool.size = -1

        self.assertRaises(ValueError, set_neg)

        def set_too_big():
            pool.size = 3

        self.assertRaises(ValueError, set_too_big)
        pool.size = 0
        self.assertEqual(pool.size, 0)
        pool.size = 2
        self.assertEqual(pool.size, 2)


class TestRef(TestCase):

    def test(self):
        pool = self.pool = ThreadPool(2)

        refs = []
        obj = SomeClass()
        obj.refs = refs
        func = obj.func
        del obj

        with greentest.disabled_gc():
            # we do this:
            #     result = func(Object(), kwarg1=Object())
            # but in a thread pool and see that arguments', result's and func's references are not leaked
            result = pool.apply(func, (Object(), ), {'kwarg1': Object()})
            assert isinstance(result, Object), repr(result)
            gevent.sleep(0.1)  # XXX should not be needed

            refs.append(weakref.ref(func))
            del func, result
            if PYPY:
                gc.collect()
                gc.collect()
            for index, r in enumerate(refs):
                assert r() is None, (index, r(), greentest.getrefcount(r()), refs)
            assert len(refs) == 4, refs


class Object(object):
    pass


class SomeClass(object):

    def func(self, arg1, kwarg1=None):
        result = Object()
        self.refs.extend([weakref.ref(x) for x in [arg1, kwarg1, result]])
        return result


def func():
    pass


class TestRefCount(TestCase):

    def test(self):
        pool = ThreadPool(1)
        pool.spawn(func)
        gevent.sleep(0)
        pool.kill()


if __name__ == '__main__':
    greentest.main()
