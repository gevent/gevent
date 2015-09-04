from greentest import TestCase, main, GenericGetTestCase
import gevent
from gevent.hub import get_hub, LoopExit
from gevent import util
from gevent import queue
from gevent.queue import Empty, Full
from gevent.event import AsyncResult


class TestQueue(TestCase):

    def test_send_first(self):
        self.switch_expected = False
        q = queue.Queue()
        q.put('hi')
        self.assertEqual(q.peek(), 'hi')
        self.assertEqual(q.get(), 'hi')

    def test_peek_empty(self):
        q = queue.Queue()
        # No putters waiting, in the main loop: LoopExit
        self.assertRaises(LoopExit, q.peek)

        def waiter(q):
            self.assertRaises(Empty, q.peek, timeout=0.01)
        g = gevent.spawn(waiter, q)
        gevent.sleep(0.1)
        g.join()

    def test_peek_multi_greenlet(self):
        q = queue.Queue()
        g = gevent.spawn(q.peek)
        g.start()
        gevent.sleep(0)
        q.put(1)
        g.join()
        self.assertTrue(g.exception is None)
        self.assertEqual(q.peek(), 1)

    def test_send_last(self):
        q = queue.Queue()

        def waiter(q):
            with gevent.Timeout(0.1):
                self.assertEqual(q.get(), 'hi2')
            return "OK"

        p = gevent.spawn(waiter, q)
        gevent.sleep(0.01)
        q.put('hi2')
        gevent.sleep(0.01)
        assert p.get(timeout=0) == "OK"

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

        p = gevent.spawn(putter, q)
        gevent.sleep(0)
        self.assertEqual(results, ['a', 'b'])
        self.assertEqual(q.get(), 'a')
        gevent.sleep(0)
        self.assertEqual(results, ['a', 'b', 'c'])
        self.assertEqual(q.get(), 'b')
        self.assertEqual(q.get(), 'c')
        assert p.get(timeout=0) == "OK"

    def test_zero_max_size(self):
        q = queue.Channel()

        def sender(evt, q):
            q.put('hi')
            evt.set('done')

        def receiver(evt, q):
            x = q.get()
            evt.set(x)

        e1 = AsyncResult()
        e2 = AsyncResult()

        p1 = gevent.spawn(sender, e1, q)
        gevent.sleep(0.001)
        self.assertTrue(not e1.ready())
        p2 = gevent.spawn(receiver, e2, q)
        self.assertEqual(e2.get(), 'hi')
        self.assertEqual(e1.get(), 'done')
        with gevent.Timeout(0):
            gevent.joinall([p1, p2])

    def test_multiple_waiters(self):
        # tests that multiple waiters get their results back
        q = queue.Queue()

        def waiter(q, evt):
            evt.set(q.get())

        sendings = ['1', '2', '3', '4']
        evts = [AsyncResult() for x in sendings]
        for i, x in enumerate(sendings):
            gevent.spawn(waiter, q, evts[i])  # XXX use waitall for them

        gevent.sleep(0.01)  # get 'em all waiting

        results = set()

        def collect_pending_results():
            for e in evts:
                with gevent.Timeout(0.001, False):
                    x = e.get()
                    results.add(x)
            return len(results)

        q.put(sendings[0])
        self.assertEqual(collect_pending_results(), 1)
        q.put(sendings[1])
        self.assertEqual(collect_pending_results(), 2)
        q.put(sendings[2])
        q.put(sendings[3])
        self.assertEqual(collect_pending_results(), 4)

    def test_waiters_that_cancel(self):
        q = queue.Queue()

        def do_receive(q, evt):
            with gevent.Timeout(0, RuntimeError()):
                try:
                    result = q.get()
                    evt.set(result)
                except RuntimeError:
                    evt.set('timed out')

        evt = AsyncResult()
        gevent.spawn(do_receive, q, evt)
        self.assertEqual(evt.get(), 'timed out')

        q.put('hi')
        self.assertEqual(q.get(), 'hi')

    def test_senders_that_die(self):
        q = queue.Queue()

        def do_send(q):
            q.put('sent')

        gevent.spawn(do_send, q)
        self.assertEqual(q.get(), 'sent')

    def test_two_waiters_one_dies(self):

        def waiter(q, evt):
            evt.set(q.get())

        def do_receive(q, evt):
            with gevent.Timeout(0, RuntimeError()):
                try:
                    result = q.get()
                    evt.set(result)
                except RuntimeError:
                    evt.set('timed out')

        q = queue.Queue()
        dying_evt = AsyncResult()
        waiting_evt = AsyncResult()
        gevent.spawn(do_receive, q, dying_evt)
        gevent.spawn(waiter, q, waiting_evt)
        gevent.sleep(0.1)
        q.put('hi')
        self.assertEqual(dying_evt.get(), 'timed out')
        self.assertEqual(waiting_evt.get(), 'hi')

    def test_two_bogus_waiters(self):
        def do_receive(q, evt):
            with gevent.Timeout(0, RuntimeError()):
                try:
                    result = q.get()
                    evt.set(result)
                except RuntimeError:
                    evt.set('timed out')

        q = queue.Queue()
        e1 = AsyncResult()
        e2 = AsyncResult()
        gevent.spawn(do_receive, q, e1)
        gevent.spawn(do_receive, q, e2)
        gevent.sleep(0.1)
        q.put('sent')
        self.assertEqual(e1.get(), 'timed out')
        self.assertEqual(e2.get(), 'timed out')
        self.assertEqual(q.get(), 'sent')


class TestChannel(TestCase):

    def test_send(self):
        channel = queue.Channel()

        events = []

        def another_greenlet():
            events.append(channel.get())
            events.append(channel.get())

        g = gevent.spawn(another_greenlet)

        events.append('sending')
        channel.put('hello')
        events.append('sent hello')
        channel.put('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)
        g.get()

    def test_wait(self):
        channel = queue.Channel()
        events = []

        def another_greenlet():
            events.append('sending hello')
            channel.put('hello')
            events.append('sending world')
            channel.put('world')
            events.append('sent world')

        g = gevent.spawn(another_greenlet)

        events.append('waiting')
        events.append(channel.get())
        events.append(channel.get())

        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world'], events)
        gevent.sleep(0)
        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world', 'sent world'], events)
        g.get()

    def test_task_done(self):
        channel = queue.JoinableQueue(0)
        X = object()
        gevent.spawn(channel.put, X)
        result = channel.get()
        assert result is X, (result, X)
        assert channel.unfinished_tasks == 1, channel.unfinished_tasks
        channel.task_done()
        assert channel.unfinished_tasks == 0, channel.unfinished_tasks


class TestNoWait(TestCase):

    def test_put_nowait_simple(self):
        result = []
        q = queue.Queue(1)

        def store_result(func, *args):
            result.append(func(*args))

        run_callback = get_hub().loop.run_callback

        run_callback(store_result, util.wrap_errors(Full, q.put_nowait), 2)
        run_callback(store_result, util.wrap_errors(Full, q.put_nowait), 3)
        gevent.sleep(0)
        assert len(result) == 2, result
        assert result[0] is None, result
        assert isinstance(result[1], queue.Full), result

    def test_get_nowait_simple(self):
        result = []
        q = queue.Queue(1)
        q.put(4)

        def store_result(func, *args):
            result.append(func(*args))

        run_callback = get_hub().loop.run_callback

        run_callback(store_result, util.wrap_errors(Empty, q.get_nowait))
        run_callback(store_result, util.wrap_errors(Empty, q.get_nowait))
        gevent.sleep(0)
        assert len(result) == 2, result
        assert result[0] == 4, result
        assert isinstance(result[1], queue.Empty), result

    # get_nowait must work from the mainloop
    def test_get_nowait_unlock(self):
        result = []
        q = queue.Queue(1)
        p = gevent.spawn(q.put, 5)

        def store_result(func, *args):
            result.append(func(*args))

        assert q.empty(), q
        gevent.sleep(0)
        assert q.full(), q
        get_hub().loop.run_callback(store_result, q.get_nowait)
        gevent.sleep(0)
        assert q.empty(), q
        assert result == [5], result
        assert p.ready(), p
        assert p.dead, p
        assert q.empty(), q

    def test_get_nowait_unlock_channel(self):
        result = []
        q = queue.Channel()
        p = gevent.spawn(q.put, 5)

        def store_result(func, *args):
            result.append(func(*args))

        assert q.empty(), q
        assert q.full(), q
        gevent.sleep(0.001)
        assert q.empty(), q
        assert q.full(), q
        get_hub().loop.run_callback(store_result, q.get_nowait)
        gevent.sleep(0.001)
        assert q.empty(), q
        assert q.full(), q
        assert result == [5], result
        assert p.ready(), p
        assert p.dead, p
        assert q.empty(), q

    # put_nowait must work from the mainloop
    def test_put_nowait_unlock(self):
        result = []
        q = queue.Queue()
        p = gevent.spawn(q.get)

        def store_result(func, *args):
            result.append(func(*args))

        assert q.empty(), q
        assert not q.full(), q
        gevent.sleep(0.001)
        assert q.empty(), q
        assert not q.full(), q
        get_hub().loop.run_callback(store_result, q.put_nowait, 10)
        assert not p.ready(), p
        gevent.sleep(0.001)
        assert result == [None], result
        assert p.ready(), p
        assert not q.full(), q
        assert q.empty(), q


class TestJoinEmpty(TestCase):

    def test_issue_45(self):
        """Test that join() exits immediatelly if not jobs were put into the queue"""
        self.switch_expected = False
        q = queue.JoinableQueue()
        q.join()


def make_get_interrupt(queue_type):

    class TestGetInterrupt(GenericGetTestCase):

        Timeout = Empty

        def wait(self, timeout):
            return queue_type().get(timeout=timeout)

    TestGetInterrupt.__name__ += '_' + queue_type.__name__
    return TestGetInterrupt


for queue_type in [queue.Queue, queue.JoinableQueue, queue.LifoQueue, queue.PriorityQueue, queue.Channel]:
    klass = make_get_interrupt(queue_type)
    globals()[klass.__name__] = klass
del klass, queue_type


def make_put_interrupt(queue):

    class TestPutInterrupt(GenericGetTestCase):

        Timeout = Full

        def wait(self, timeout):
            while not queue.full():
                queue.put(1)
            return queue.put(2, timeout=timeout)

    TestPutInterrupt.__name__ += '_' + queue.__class__.__name__
    return TestPutInterrupt


for obj in [queue.Queue(1), queue.JoinableQueue(1), queue.LifoQueue(1), queue.PriorityQueue(1), queue.Channel()]:
    klass = make_put_interrupt(obj)
    globals()[klass.__name__] = klass
del klass, obj


del GenericGetTestCase


if __name__ == '__main__':
    main()
