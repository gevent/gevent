from time import time
import gevent
from gevent import pool
from gevent.event import Event
import greentest


class TestCoroutinePool(greentest.TestCase):
    klass = pool.Pool

    def test_apply_async(self):
        done = Event()

        def some_work(x):
            done.set()

        pool = self.klass(2)
        pool.apply_async(some_work, ('x', ))
        done.wait()

    def test_apply(self):
        value = 'return value'

        def some_work():
            return value

        pool = self.klass(2)
        result = pool.apply(some_work)
        self.assertEqual(value, result)

    def test_multiple_coros(self):
        evt = Event()
        results = []

        def producer():
            results.append('prod')
            evt.set()

        def consumer():
            results.append('cons1')
            evt.wait()
            results.append('cons2')

        pool = self.klass(2)
        done = pool.spawn(consumer)
        pool.apply_async(producer)
        done.get()
        self.assertEquals(['cons1', 'prod', 'cons2'], results)

    def dont_test_timer_cancel(self):
        timer_fired = []

        def fire_timer():
            timer_fired.append(True)

        def some_work():
            gevent.timer(0, fire_timer)

        pool = self.klass(2)
        pool.apply(some_work)
        gevent.sleep(0)
        self.assertEquals(timer_fired, [])

    def test_reentrant(self):
        pool = self.klass(1)

        def reenter():
            result = pool.apply(lambda a: a, ('reenter', ))
            self.assertEqual('reenter', result)

        pool.apply(reenter)

        evt = Event()

        def reenter_async():
            pool.apply_async(lambda a: a, ('reenter', ))
            evt.set()

        pool.apply_async(reenter_async)
        evt.wait()

    def test_stderr_raising(self):
        # testing that really egregious errors in the error handling code
        # (that prints tracebacks to stderr) don't cause the pool to lose
        # any members
        import sys
        pool = self.klass(size=1)

        # we're going to do this by causing the traceback.print_exc in
        # safe_apply to raise an exception and thus exit _main_loop
        normal_err = sys.stderr
        try:
            sys.stderr = FakeFile()
            waiter = pool.spawn(crash)
            self.assertRaises(RuntimeError, waiter.get)
            # the pool should have something free at this point since the
            # waiter returned
            # pool.Pool change: if an exception is raised during execution of a link,
            # the rest of the links are scheduled to be executed on the next hub iteration
            # this introduces a delay in updating pool.sem which makes pool.free_count() report 0
            # therefore, sleep:
            gevent.sleep(0)
            self.assertEqual(pool.free_count(), 1)
            # shouldn't block when trying to get
            t = gevent.Timeout.start_new(0.1)
            try:
                pool.apply(gevent.sleep, (0, ))
            finally:
                t.cancel()
        finally:
            sys.stderr = normal_err
            pool.join()


def crash(*args, **kw):
    raise RuntimeError("Whoa")


class FakeFile(object):
    write = crash


class PoolBasicTests(greentest.TestCase):
    klass = pool.Pool

    def test_execute_async(self):
        p = self.klass(size=2)
        self.assertEqual(p.free_count(), 2)
        r = []

        first = p.spawn(r.append, 1)
        self.assertEqual(p.free_count(), 1)
        first.get()
        self.assertEqual(r, [1])
        gevent.sleep(0)
        self.assertEqual(p.free_count(), 2)

        #Once the pool is exhausted, calling an execute forces a yield.

        p.apply_async(r.append, (2, ))
        self.assertEqual(1, p.free_count())
        self.assertEqual(r, [1])

        p.apply_async(r.append, (3, ))
        self.assertEqual(0, p.free_count())
        self.assertEqual(r, [1])

        p.apply_async(r.append, (4, ))
        self.assertEqual(r, [1])
        gevent.sleep(0.01)
        self.assertEqual(r, [1, 2, 3, 4])

    def test_execute(self):
        p = self.klass()
        result = p.apply(lambda a: ('foo', a), (1, ))
        self.assertEqual(result, ('foo', 1))

    def test_init_zerosize(self):
        self.switch_expected = False
        self.assertRaises(ValueError, self.klass, 0)

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
    gevent.sleep(wait)
    return x * x

TIMEOUT1, TIMEOUT2, TIMEOUT3 = 0.082, 0.035, 0.14


class TestPool(greentest.TestCase):
    __timeout__ = 5
    size = 1

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.pool = pool.Pool(self.size)

    def cleanup(self):
        self.pool.join()

    def test_apply(self):
        papply = self.pool.apply
        self.assertEqual(papply(sqr, (5,)), sqr(5))
        self.assertEqual(papply(sqr, (), {'x': 3}), sqr(x=3))

    def test_map(self):
        pmap = self.pool.map
        self.assertEqual(pmap(sqr, range(10)), map(sqr, range(10)))
        self.assertEqual(pmap(sqr, range(100)), map(sqr, range(100)))

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
        self.assertEqual(list(it), map(sqr, range(10)))

        it = self.pool.imap(sqr, range(10))
        for i in range(10):
            self.assertEqual(it.next(), i * i)
        self.assertRaises(StopIteration, it.next)

        it = self.pool.imap(sqr, range(1000))
        for i in range(1000):
            self.assertEqual(it.next(), i * i)
        self.assertRaises(StopIteration, it.next)

    def test_imap_unordered(self):
        it = self.pool.imap_unordered(sqr, range(1000))
        self.assertEqual(sorted(it), map(sqr, range(1000)))

        it = self.pool.imap_unordered(sqr, range(1000))
        self.assertEqual(sorted(it), map(sqr, range(1000)))

    def test_terminate(self):
        result = self.pool.map_async(gevent.sleep, [0.1] * ((self.size or 10) * 2))
        gevent.sleep(0.1)
        kill = TimingWrapper(self.pool.kill)
        kill()
        assert kill.elapsed < 0.5, kill.elapsed
        result.join()

    def sleep(self, x):
        gevent.sleep(float(x) / 10.)
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


class TestPool3(TestPool):
    size = 3


class TestPool10(TestPool):
    size = 10


class TestPoolUnlimit(TestPool):
    size = None


class TestJoinSleep(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        p = pool.Pool()
        g = p.spawn(gevent.sleep, 10)
        try:
            p.join(timeout=timeout)
        finally:
            g.kill()


class TestJoinSleep_raise_error(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        p = pool.Pool()
        g = p.spawn(gevent.sleep, 10)
        try:
            p.join(timeout=timeout, raise_error=True)
        finally:
            g.kill()


class TestJoinEmpty(greentest.TestCase):
    switch_expected = False

    def test(self):
        p = pool.Pool()
        p.join()


class TestSpawn(greentest.TestCase):
    switch_expected = True

    def test(self):
        p = pool.Pool(1)
        self.assertEqual(len(p), 0)
        p.spawn(gevent.sleep, 0.1)
        self.assertEqual(len(p), 1)
        p.spawn(gevent.sleep, 0.1)  # this spawn blocks until the old one finishes
        self.assertEqual(len(p), 1)
        gevent.sleep(0.19)
        self.assertEqual(len(p), 0)


if __name__ == '__main__':
    greentest.main()
