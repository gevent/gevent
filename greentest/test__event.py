import greentest
import gevent
from gevent.event import Event, AsyncResult

DELAY = 0.01


class TestEventWait(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        Event().wait(timeout=timeout)


class TestAsyncResultWait(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        AsyncResult().wait(timeout=timeout)


class TestAsyncResultGet(greentest.GenericGetTestCase):

    def wait(self, timeout):
        AsyncResult().get(timeout=timeout)


class TestAsyncResult(greentest.TestCase):

    def test_set_exc(self):
        log = []
        e = AsyncResult()

        def waiter():
            try:
                result = e.get()
                log.append(('received', result))
            except Exception, ex:
                log.append(('catched', ex))
        gevent.spawn(waiter)
        obj = Exception()
        e.set_exception(obj)
        gevent.sleep(0)
        assert log == [('catched', obj)], log

    def test_set(self):
        event1 = AsyncResult()
        event2 = AsyncResult()

        g = gevent.spawn_later(DELAY / 2.0, event1.set, 'hello event1')
        t = gevent.Timeout.start_new(0, ValueError('interrupted'))
        try:
            try:
                result = event1.get()
            except ValueError:
                X = object()
                result = gevent.with_timeout(DELAY, event2.get, timeout_value=X)
                assert result is X, 'Nobody sent anything to event2 yet it received %r' % (result, )
        finally:
            t.cancel()
            g.kill()


class TestAsync_ResultAsLinkTarget(greentest.TestCase):

    def test_set(self):
        g = gevent.spawn(lambda: 1)
        s1, s2, s3 = AsyncResult(), AsyncResult(), AsyncResult()
        g.link(s1)
        g.link_value(s2)
        g.link_exception(s3)
        assert s1.get() == 1
        assert s2.get() == 1
        assert gevent.with_timeout(DELAY, s3.get, timeout_value=X) is X

    def test_set_exception(self):
        def func():
            raise greentest.ExpectedException('TestAsync_ResultAsLinkTarget.test_set_exception')
        g = gevent.spawn(func)
        s1, s2, s3 = AsyncResult(), AsyncResult(), AsyncResult()
        g.link(s1)
        g.link_value(s2)
        g.link_exception(s3)
        self.assertRaises(greentest.ExpectedException, s1.get)
        assert gevent.with_timeout(DELAY, s2.get, timeout_value=X) is X
        self.assertRaises(greentest.ExpectedException, s3.get)


class TestEvent_SetThenClear(greentest.TestCase):
    N = 1

    def test(self):
        e = Event()
        waiters = [gevent.spawn(e.wait) for i in xrange(self.N)]
        gevent.sleep(0.001)
        e.set()
        e.clear()
        for t in waiters:
            t.join()


class TestEvent_SetThenClear100(TestEvent_SetThenClear):
    N = 100


class TestEvent_SetThenClear1000(TestEvent_SetThenClear):
    N = 1000


X = object()

if __name__ == '__main__':
    greentest.main()
