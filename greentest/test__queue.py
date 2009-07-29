import random
from greentest import TestCase, main
import gevent
from gevent import proc, coros, core
from gevent import queue


class TestQueue(TestCase):

    def test_send_first(self):
        self.disable_switch_check()
        q = queue.Queue()
        q.put('hi')
        self.assertEquals(q.get(), 'hi')

    def test_send_last(self):
        q = queue.Queue()
        def waiter(q):
            timer = gevent.Timeout(0.1)
            try:
                self.assertEquals(q.get(), 'hi2')
            finally:
                timer.cancel()
            return "OK"

        p = proc.spawn(waiter, q)
        gevent.sleep(0.01)
        q.put('hi2')
        gevent.sleep(0.01)
        assert p.wait(timeout=0)=="OK"

    def test_max_size(self):
        q = queue.Queue(2)
        results = []

        def putter(q):
            q.put('a')
            results.append('a')
            q.put('b')
            results.append('b')
            q.put('c')
            results.append('c')
            return "OK"

        p = proc.spawn(putter, q)
        gevent.sleep(0)
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals(q.get(), 'a')
        gevent.sleep(0)
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals(q.get(), 'b')
        self.assertEquals(q.get(), 'c')
        assert p.wait(timeout=0)=="OK"

    def test_zero_max_size(self):
        q = queue.Queue(0)
        def sender(evt, q):
            q.put('hi')
            evt.send('done')

        def receiver(evt, q):
            x = q.get()
            evt.send(x)

        e1 = coros.event()
        e2 = coros.event()

        p1 = proc.spawn(sender, e1, q)
        gevent.sleep(0.001)
        self.assert_(not e1.ready())
        p2 = proc.spawn(receiver, e2, q)
        self.assertEquals(e2.wait(),'hi')
        self.assertEquals(e1.wait(),'done')
        timeout = gevent.Timeout(0)
        try:
            proc.waitall([p1, p2])
        finally:
            timeout.cancel()

    def test_multiple_waiters(self):
        # tests that multiple waiters get their results back
        q = queue.Queue()

        def waiter(q, evt):
            evt.send(q.get())

        sendings = ['1', '2', '3', '4']
        evts = [coros.event() for x in sendings]
        for i, x in enumerate(sendings):
            gevent.spawn(waiter, q, evts[i]) # use proc and waitall for them

        gevent.sleep(0.01) # get 'em all waiting

        results = set()
        def collect_pending_results():
            for i, e in enumerate(evts):
                timer = gevent.Timeout(0.001)
                try:
                    x = e.wait()
                    results.add(x)
                    timer.cancel()
                except gevent.Timeout:
                    pass  # no pending result at that event
            return len(results)
        q.put(sendings[0])
        self.assertEquals(collect_pending_results(), 1)
        q.put(sendings[1])
        self.assertEquals(collect_pending_results(), 2)
        q.put(sendings[2])
        q.put(sendings[3])
        self.assertEquals(collect_pending_results(), 4)

    def test_waiters_that_cancel(self):
        q = queue.Queue()

        def do_receive(q, evt):
            gevent.Timeout(0, RuntimeError())
            try:
                result = q.get()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')

        evt = coros.event()
        gevent.spawn(do_receive, q, evt)
        self.assertEquals(evt.wait(), 'timed out')

        q.put('hi')
        self.assertEquals(q.get(), 'hi')

    def test_senders_that_die(self):
        q = queue.Queue()

        def do_send(q):
            q.put('sent')

        gevent.spawn(do_send, q)
        self.assertEquals(q.get(), 'sent')

    def test_two_waiters_one_dies(self):
        def waiter(q, evt):
            evt.send(q.get())
        def do_receive(q, evt):
            timeout = gevent.Timeout(0, RuntimeError())
            try:
                try:
                    result = q.get()
                    evt.send(result)
                except RuntimeError:
                    evt.send('timed out')
            finally:
                timeout.cancel()

        q = queue.Queue()
        dying_evt = coros.event()
        waiting_evt = coros.event()
        gevent.spawn(do_receive, q, dying_evt)
        gevent.spawn(waiter, q, waiting_evt)
        gevent.sleep(0)
        q.put('hi')
        self.assertEquals(dying_evt.wait(), 'timed out')
        self.assertEquals(waiting_evt.wait(), 'hi')

    def test_two_bogus_waiters(self):
        def do_receive(q, evt):
            gevent.Timeout(0, RuntimeError())
            try:
                result = q.get()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')
            # XXX finally = timeout

        q = queue.Queue()
        e1 = coros.event()
        e2 = coros.event()
        gevent.spawn(do_receive, q, e1)
        gevent.spawn(do_receive, q, e2)
        gevent.sleep(0)
        q.put('sent')
        self.assertEquals(e1.wait(), 'timed out')
        self.assertEquals(e2.wait(), 'timed out')
        self.assertEquals(q.get(), 'sent')


class TestChannel(TestCase):

    def test_send(self):
        channel = queue.Queue(0)

        events = []

        def another_greenlet():
            events.append(channel.get())
            events.append(channel.get())

        g = proc.spawn(another_greenlet)

        events.append('sending')
        channel.put('hello')
        events.append('sent hello')
        channel.put('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)
        g.wait()

    def test_wait(self):
        channel = queue.Queue(0)
        events = []

        def another_greenlet():
            events.append('sending hello')
            channel.put('hello')
            events.append('sending world')
            channel.put('world')
            events.append('sent world')

        g = proc.spawn(another_greenlet)

        events.append('waiting')
        events.append(channel.get())
        events.append(channel.get())

        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world'], events)
        gevent.sleep(0)
        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world', 'sent world'], events)
        g.wait()


class TestNoWait(TestCase):

    def test_put_nowait_simple(self):
        result = []
        q = queue.Queue(1)
        def store_result(func, *args):
            result.append(func(*args))
        core.active_event(store_result, proc.wrap_errors(Exception, q.put_nowait), 2)
        core.active_event(store_result, proc.wrap_errors(Exception, q.put_nowait), 3)
        gevent.sleep(0)
        assert len(result)==2, result
        assert result[0]==None, result
        assert isinstance(result[1], queue.Full), result

    def test_get_nowait_simple(self):
        result = []
        q = queue.Queue(1)
        q.put(4)
        def store_result(func, *args):
            result.append(func(*args))
        core.active_event(store_result, proc.wrap_errors(Exception, q.get_nowait))
        core.active_event(store_result, proc.wrap_errors(Exception, q.get_nowait))
        gevent.sleep(0)
        assert len(result)==2, result
        assert result[0]==4, result
        assert isinstance(result[1], queue.Empty), result

    # get_nowait must work from the mainloop
    def test_get_nowait_unlock(self):
        result = []
        q = queue.Queue(0)
        p = proc.spawn(q.put, 5)
        def store_result(func, *args):
            result.append(func(*args))
        assert q.empty(), q
        assert q.full(), q
        gevent.sleep(0)
        assert not q.empty(), q
        assert q.full(), q
        core.active_event(store_result, proc.wrap_errors(Exception, q.get_nowait))
        gevent.sleep(0)
        assert q.empty(), q
        assert q.full(), q
        assert result == [5], result
        assert p.ready(), p
        assert p.dead, p
        assert q.empty(), q

    # put_nowait must work from the mainloop
    def test_put_nowait_unlock(self):
        result = []
        q = queue.Queue(0)
        p = proc.spawn(q.get)
        def store_result(func, *args):
            result.append(func(*args))
        assert q.empty(), q
        assert q.full(), q
        gevent.sleep(0)
        assert q.empty(), q
        assert not q.full(), q
        core.active_event(store_result, proc.wrap_errors(Exception, q.put_nowait), 10)
        assert not p.ready(), p
        gevent.sleep(0)
        assert result == [None], result
        assert p.ready(), p
        assert q.full(), q
        assert q.empty(), q


if __name__=='__main__':
    main()
