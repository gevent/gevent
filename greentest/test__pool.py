import gevent
from gevent import pool
from gevent.event import Event
from greentest import TestCase, main

class TestCoroutinePool(TestCase):
    klass = pool.Pool

    def test_execute_async(self):
        done = Event()
        def some_work(x):
            print 'puttin'
            done.put()
            print 'done putting'
        pool = self.klass(2)
        pool.execute_async(some_work, 'x')
        done.get()

    def test_execute(self):
        value = 'return value'
        def some_work():
            return value
        pool = self.klass(2)
        worker = pool.execute(some_work)
        self.assertEqual(value, worker.get())

    def test_multiple_coros(self):
        evt = Event()
        results = []
        def producer():
            results.append('prod')
            evt.put()

        def consumer():
            results.append('cons1')
            evt.get()
            results.append('cons2')

        pool = self.klass(2)
        done = pool.execute(consumer)
        pool.execute_async(producer)
        done.get()
        self.assertEquals(['cons1', 'prod', 'cons2'], results)

    def dont_test_timer_cancel(self):
        timer_fired = []
        def fire_timer():
            timer_fired.append(True)
        def some_work():
            gevent.timer(0, fire_timer)
        pool = self.klass(2)
        worker = pool.execute(some_work)
        worker.get()
        gevent.sleep(0)
        self.assertEquals(timer_fired, [])

    def test_reentrant(self):
        pool = self.klass(1)
        def reenter():
            waiter = pool.execute(lambda a: a, 'reenter')
            self.assertEqual('reenter', waiter.get())

        outer_waiter = pool.execute(reenter)
        outer_waiter.get()

        evt = Event()
        def reenter_async():
            pool.execute_async(lambda a: a, 'reenter')
            evt.put('done')

        pool.execute_async(reenter_async)
        evt.get()

    def test_stderr_raising(self):
        # testing that really egregious errors in the error handling code
        # (that prints tracebacks to stderr) don't cause the pool to lose
        # any members
        import sys
        pool = self.klass(size=1)
        def crash(*args, **kw):
            raise RuntimeError("Whoa")
        class FakeFile(object):
            write = crash

        # we're going to do this by causing the traceback.print_exc in
        # safe_apply to raise an exception and thus exit _main_loop
        normal_err = sys.stderr
        try:
            sys.stderr = FakeFile()
            waiter = pool.execute(crash)
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
            t = gevent.Timeout(0.1)
            try:
                pool.execute(gevent.sleep, 1)
            finally:
                t.cancel()
        finally:
            sys.stderr = normal_err


class PoolBasicTests(TestCase):
    klass = pool.Pool

    def test_execute_async(self):
        p = self.klass(size=2)
        self.assertEqual(p.free_count(), 2)
        r = []
        def foo(a):
            r.append(a)
        evt = p.execute(foo, 1)
        self.assertEqual(p.free_count(), 1)
        evt.get()
        self.assertEqual(r, [1])
        gevent.sleep(0)
        self.assertEqual(p.free_count(), 2)

        #Once the pool is exhausted, calling an execute forces a yield.

        p.execute_async(foo, 2)
        self.assertEqual(1, p.free_count())
        self.assertEqual(r, [1])

        p.execute_async(foo, 3)
        self.assertEqual(0, p.free_count())
        self.assertEqual(r, [1])

        p.execute_async(foo, 4)
        self.assertEqual(r, [1])
        gevent.sleep(0.01)
        self.assertEqual(r, [1,2,3,4])

    def test_execute(self):
        p = self.klass()
        evt = p.execute(lambda a: ('foo', a), 1)
        self.assertEqual(evt.get(), ('foo', 1))


if __name__=='__main__':
    main()

