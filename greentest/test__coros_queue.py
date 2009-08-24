from greentest import TestCase
from greentest import main
import gevent
from gevent import coros

import warnings
warnings.simplefilter('ignore', DeprecationWarning)

class TestQueue(TestCase):

    def test_send_first(self):
        self.switch_expected = False
        q = coros.Queue()
        q.send('hi')
        self.assertEquals(q.wait(), 'hi')

    def test_send_exception_first(self):
        self.switch_expected = False
        q = coros.Queue()
        q.send(exc=RuntimeError())
        self.assertRaises(RuntimeError, q.wait)

    def test_send_last(self):
        q = coros.Queue()
        def waiter(q):
            timer = gevent.Timeout.start_new(0.1)
            self.assertEquals(q.wait(), 'hi2')
            timer.cancel()

        gevent.spawn(waiter, q)
        gevent.sleep(0)
        gevent.sleep(0)
        q.send('hi2')
        gevent.sleep(0)

    def test_max_size(self):
        q = coros.Channel(2)
        results = []

        def putter(q):
            q.send('a')
            results.append('a')
            q.send('b')
            results.append('b')
            q.send('c')
            results.append('c')

        gevent.spawn(putter, q)
        gevent.sleep(0)
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals(q.wait(), 'a')
        gevent.sleep(0)
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals(q.wait(), 'b')
        self.assertEquals(q.wait(), 'c')
        gevent.sleep(0)

    def test_zero_max_size(self):
        q = coros.Channel()
        def sender(evt, q):
            q.send('hi')
            evt.send('done')

        def receiver(evt, q):
            x = q.wait()
            evt.send(x)

        e1 = coros.event()
        e2 = coros.event()

        gevent.spawn(sender, e1, q)
        gevent.sleep(0)
        self.assert_(not e1.ready())
        gevent.spawn(receiver, e2, q)
        self.assertEquals(e2.wait(),'hi')
        self.assertEquals(e1.wait(),'done')

    def test_multiple_waiters(self):
        # tests that multiple waiters get their results back
        q = coros.Queue()

        def waiter(q, evt):
            evt.send(q.wait())

        sendings = ['1', '2', '3', '4']
        evts = [coros.event() for x in sendings]
        for i, x in enumerate(sendings):
            gevent.spawn(waiter, q, evts[i])

        gevent.sleep(0.01) # get 'em all waiting

        results = set()
        def collect_pending_results():
            for i, e in enumerate(evts):
                timer = gevent.Timeout.start_new(0.001)
                try:
                    x = e.wait()
                    results.add(x)
                    timer.cancel()
                except gevent.Timeout:
                    pass  # no pending result at that event
            return len(results)
        q.send(sendings[0])
        self.assertEquals(collect_pending_results(), 1)
        q.send(sendings[1])
        self.assertEquals(collect_pending_results(), 2)
        q.send(sendings[2])
        q.send(sendings[3])
        self.assertEquals(collect_pending_results(), 4)

    def test_waiters_that_cancel(self):
        q = coros.Queue()

        def do_receive(q, evt):
            gevent.Timeout.start_new(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')


        evt = coros.event()
        gevent.spawn(do_receive, q, evt)
        self.assertEquals(evt.wait(), 'timed out')

        q.send('hi')
        self.assertEquals(q.wait(), 'hi')

    def test_senders_that_die(self):
        q = coros.Queue()

        def do_send(q):
            q.send('sent')

        gevent.spawn(do_send, q)
        self.assertEquals(q.wait(), 'sent')

    def test_two_waiters_one_dies(self):
        def waiter(q, evt):
            evt.send(q.wait())
        def do_receive(q, evt):
            gevent.Timeout.start_new(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')

        q = coros.Queue()
        dying_evt = coros.event()
        waiting_evt = coros.event()
        gevent.spawn(do_receive, q, dying_evt)
        gevent.spawn(waiter, q, waiting_evt)
        gevent.sleep(0)
        q.send('hi')
        self.assertEquals(dying_evt.wait(), 'timed out')
        self.assertEquals(waiting_evt.wait(), 'hi')

    def test_two_bogus_waiters(self):
        def do_receive(q, evt):
            gevent.Timeout.start_new(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')

        q = coros.Queue()
        e1 = coros.event()
        e2 = coros.event()
        gevent.spawn(do_receive, q, e1)
        gevent.spawn(do_receive, q, e2)
        gevent.sleep(0)
        q.send('sent')
        self.assertEquals(e1.wait(), 'timed out')
        self.assertEquals(e2.wait(), 'timed out')
        self.assertEquals(q.wait(), 'sent')

#     def test_waiting(self):
#         def do_wait(q, evt):
#             result = q.wait()
#             evt.send(result)
#
#         q = coros.Queue()
#         e1 = coros.event()
#         gevent.spawn(do_wait, q, e1)
#         gevent.sleep(0)
#         self.assertEquals(1, q.waiting())
#         q.send('hi')
#         gevent.sleep(0)
#         self.assertEquals(0, q.waiting())
#         self.assertEquals('hi', e1.wait())
#         self.assertEquals(0, q.waiting())


class TestChannel(TestCase):

    def test_send(self):
        channel = coros.Channel()

        events = []

        def another_greenlet():
            events.append(channel.wait())
            events.append(channel.wait())

        g = gevent.spawn(another_greenlet)

        events.append('sending')
        channel.send('hello')
        events.append('sent hello')
        channel.send('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)
        if channel._timer is not None:
            gevent.sleep(0)

    def test_wait(self):
        channel = coros.Channel()
        events = []

        def another_greenlet():
            events.append('sending hello')
            channel.send('hello')
            events.append('sending world')
            channel.send('world')
            events.append('sent world')

        g = gevent.spawn(another_greenlet)

        events.append('waiting')
        events.append(channel.wait())
        events.append(channel.wait())

        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world'], events)
        gevent.sleep(0)
        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world', 'sent world'], events)
        g.get(block=False)


if __name__=='__main__':
    main()
