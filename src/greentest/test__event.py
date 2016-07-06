import greentest
import gevent
from gevent.event import Event, AsyncResult
from _six import xrange

DELAY = 0.01


class TestEventWait(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        Event().wait(timeout=timeout)

    def test_cover(self):
        str(Event())


class TestWaitEvent(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        gevent.wait([Event()], timeout=timeout)

    def test_set_during_wait(self):
        # https://github.com/gevent/gevent/issues/771
        # broke in the refactoring. we must not add new links
        # while we're running the callback

        event = Event()

        def setter():
            event.set()

        def waiter():
            s = gevent.spawn(setter)
            # let the setter set() the event;
            # when this method returns we'll be running in the Event._notify_links callback
            # (that is, it switched to us)
            res = event.wait()
            self.assertTrue(res)
            self.assertTrue(event.ready())
            s.join() # make sure it's dead
            # Clear the event. Now we can't wait for the event without
            # another set to happen.
            event.clear()
            self.assertFalse(event.ready())

            # Before the bug fix, this would return "immediately" with
            # event in the result list, because the _notify_links loop would
            # immediately add the waiter and call it
            o = gevent.wait((event,), timeout=0.01)
            self.assertFalse(event.ready())
            self.assertFalse(event in o, o)

        gevent.spawn(waiter).join()


class TestAsyncResultWait(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        AsyncResult().wait(timeout=timeout)


class TestWaitAsyncResult(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        gevent.wait([AsyncResult()], timeout=timeout)


class TestAsyncResultGet(greentest.GenericGetTestCase):

    def wait(self, timeout):
        AsyncResult().get(timeout=timeout)


class TestAsyncResult(greentest.TestCase):

    def test_link(self):
        ar = AsyncResult()
        self.assertRaises(TypeError, ar.rawlink, None)
        ar.unlink(None) # doesn't raise
        ar.unlink(None) # doesn't raise
        str(ar) # cover

    def test_set_exc(self):
        log = []
        e = AsyncResult()
        self.assertEqual(e.exc_info, ())
        self.assertEqual(e.exception, None)

        def waiter():
            try:
                result = e.get()
                log.append(('received', result))
            except Exception as ex:
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

    def test_nonblocking_get(self):
        ar = AsyncResult()
        self.assertRaises(gevent.Timeout, ar.get, block=False)
        self.assertRaises(gevent.Timeout, ar.get_nowait)


class TestAsyncResultAsLinkTarget(greentest.TestCase):
    error_fatal = False

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
            raise greentest.ExpectedException('TestAsyncResultAsLinkTarget.test_set_exception')
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
        waiters = [gevent.spawn(e.wait) for i in range(self.N)]
        gevent.sleep(0.001)
        e.set()
        e.clear()
        for t in waiters:
            t.join()


class TestEvent_SetThenClear100(TestEvent_SetThenClear):
    N = 100


class TestEvent_SetThenClear1000(TestEvent_SetThenClear):
    N = 1000


class TestWait(greentest.TestCase):
    N = 5
    count = None
    timeout = 1
    period = timeout / 100.0

    def _sender(self, events, asyncs):
        while events or asyncs:
            gevent.sleep(self.period)
            if events:
                events.pop().set()
            gevent.sleep(self.period)
            if asyncs:
                asyncs.pop().set()

    @greentest.skipOnAppVeyor("Not all results have arrived sometimes due to timer issues")
    def test(self):
        events = [Event() for _ in xrange(self.N)]
        asyncs = [AsyncResult() for _ in xrange(self.N)]
        max_len = len(events) + len(asyncs)
        sender = gevent.spawn(self._sender, events, asyncs)
        results = gevent.wait(events + asyncs, count=self.count, timeout=self.timeout)
        if self.timeout is None:
            expected_len = max_len
        else:
            expected_len = min(max_len, self.timeout / self.period)
        if self.count is None:
            assert sender.ready()
        else:
            expected_len = min(self.count, expected_len)
            assert not sender.ready()
            sender.kill()
        self.assertEqual(expected_len, len(results), (expected_len, len(results), results))


class TestWait_notimeout(TestWait):
    timeout = None


class TestWait_count1(TestWait):
    count = 1


class TestWait_count2(TestWait):
    count = 2


X = object()

if __name__ == '__main__':
    greentest.main()
