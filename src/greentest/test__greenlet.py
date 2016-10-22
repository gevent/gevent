# Copyright (c) 2008-2009 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import greentest
import gevent
import re
from gevent import sleep, with_timeout, getcurrent
from gevent import greenlet
from gevent.event import AsyncResult
from gevent.queue import Queue, Channel

DELAY = 0.01
greentest.TestCase.error_fatal = False


class ExpectedError(greentest.ExpectedException):
    pass


class TestLink(greentest.TestCase):

    def assertRaises(self, err, func, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except:
            ex = sys.exc_info()[1]
            if ex is err:
                return
            if isinstance(ex, err):
                return
            raise
        raise AssertionError('%s not raised, returned %r' % (err, result))

    def test_link_to_asyncresult(self):
        p = gevent.spawn(lambda: 100)
        event = AsyncResult()
        p.link(event)
        self.assertEqual(event.get(), 100)

        for i in range(3):
            event2 = AsyncResult()
            p.link(event2)
            self.assertEqual(event2.get(), 100)

    def test_link_to_asyncresult_exception(self):
        err = ExpectedError('test_link_to_asyncresult_exception')
        p = gevent.spawn(lambda: getcurrent().throw(err))
        event = AsyncResult()
        p.link(event)
        self.assertRaises(err, event.get)

        for i in range(3):
            event2 = AsyncResult()
            p.link(event2)
            self.assertRaises(err, event2.get)

    def test_link_to_queue(self):
        p = gevent.spawn(lambda: 100)
        q = Queue()
        p.link(q.put)
        self.assertEqual(q.get().get(), 100)

        for i in range(3):
            p.link(q.put)
            self.assertEqual(q.get().get(), 100)

    def test_link_to_channel(self):
        p1 = gevent.spawn(lambda: 101)
        p2 = gevent.spawn(lambda: 102)
        p3 = gevent.spawn(lambda: 103)
        q = Channel()
        p1.link(q.put)
        p2.link(q.put)
        p3.link(q.put)
        results = [q.get().get(), q.get().get(), q.get().get()]
        assert sorted(results) == [101, 102, 103], results


class TestUnlink(greentest.TestCase):
    switch_expected = False

    def _test_func(self, p, link):
        link(dummy_test_func)
        assert len(p._links) == 1, p._links
        p.unlink(dummy_test_func)
        assert not p._links, p._links

        link(self.setUp)
        assert len(p._links) == 1, p._links
        p.unlink(self.setUp)
        assert not p._links, p._links
        p.kill()

    def test_func_link(self):
        p = gevent.spawn(dummy_test_func)
        self._test_func(p, p.link)

    def test_func_link_value(self):
        p = gevent.spawn(dummy_test_func)
        self._test_func(p, p.link_value)

    def test_func_link_exception(self):
        p = gevent.spawn(dummy_test_func)
        self._test_func(p, p.link_exception)


class LinksTestCase(greentest.TestCase):

    def link(self, p, listener=None):
        getattr(p, self.link_method)(listener)

    def set_links(self, p):
        event = AsyncResult()
        self.link(p, event)

        queue = Queue(1)
        self.link(p, queue.put)

        callback_flag = ['initial']
        self.link(p, lambda *args: callback_flag.remove('initial'))

        for _ in range(10):
            self.link(p, AsyncResult())
            self.link(p, Queue(1).put)

        return event, queue, callback_flag

    def set_links_timeout(self, link):
        # stuff that won't be touched
        event = AsyncResult()
        link(event)

        queue = Channel()
        link(queue.put)
        return event, queue

    def check_timed_out(self, event, queue):
        assert with_timeout(DELAY, event.get, timeout_value=X) is X, repr(event.get())
        assert with_timeout(DELAY, queue.get, timeout_value=X) is X, queue.get()


def return25():
    return 25


def sleep0():
    return sleep(0)


class TestReturn_link(LinksTestCase):
    link_method = 'link'

    def cleanup(self):
        while self.p._links:
            self.p._links.pop()

    def test_return(self):
        self.p = gevent.spawn(return25)
        for _ in range(3):
            self._test_return(self.p, 25, sleep0)
        self.p.kill()

    def _test_return(self, p, result, action):
        event, queue, callback_flag = self.set_links(p)

        # stuff that will time out because there's no unhandled exception:
        xxxxx = self.set_links_timeout(p.link_exception)

        sleep(DELAY * 2)
        assert not p, p

        self.assertEqual(event.get(), result)
        self.assertEqual(queue.get().get(), result)

        sleep(DELAY)
        assert not callback_flag, callback_flag

        self.check_timed_out(*xxxxx)

    def _test_kill(self, p):
        event, queue, callback_flag = self.set_links(p)
        xxxxx = self.set_links_timeout(p.link_exception)

        p.kill()
        sleep(DELAY)
        assert not p, p

        assert isinstance(event.get(), greenlet.GreenletExit), event.get()
        assert isinstance(queue.get().get(), greenlet.GreenletExit), queue.get().get()

        sleep(DELAY)
        assert not callback_flag, callback_flag

        self.check_timed_out(*xxxxx)

    def test_kill(self):
        p = self.p = gevent.spawn(sleep, DELAY)
        for _ in range(3):
            self._test_kill(p)


class TestReturn_link_value(TestReturn_link):
    link_method = 'link_value'


class TestRaise_link(LinksTestCase):
    link_method = 'link'

    def _test_raise(self, p):
        event, queue, callback_flag = self.set_links(p)
        xxxxx = self.set_links_timeout(p.link_value)

        sleep(DELAY)
        assert not p, p

        self.assertRaises(ExpectedError, event.get)
        self.assertEqual(queue.get(), p)
        sleep(DELAY)
        assert not callback_flag, callback_flag

        self.check_timed_out(*xxxxx)

    def test_raise(self):
        p = self.p = gevent.spawn(lambda: getcurrent().throw(ExpectedError('test_raise')))
        for _ in range(3):
            self._test_raise(p)


class TestRaise_link_exception(TestRaise_link):
    link_method = 'link_exception'


class TestStuff(greentest.TestCase):

    def test_wait_noerrors(self):
        x = gevent.spawn(lambda: 1)
        y = gevent.spawn(lambda: 2)
        z = gevent.spawn(lambda: 3)
        gevent.joinall([x, y, z], raise_error=True)
        self.assertEqual([x.value, y.value, z.value], [1, 2, 3])
        e = AsyncResult()
        x.link(e)
        self.assertEqual(e.get(), 1)
        x.unlink(e)
        e = AsyncResult()
        x.link(e)
        self.assertEqual(e.get(), 1)

    def test_wait_error(self):

        def x():
            sleep(DELAY)
            return 1
        x = gevent.spawn(x)
        y = gevent.spawn(lambda: getcurrent().throw(ExpectedError('test_wait_error')))
        self.assertRaises(ExpectedError, gevent.joinall, [x, y], raise_error=True)
        self.assertRaises(ExpectedError, gevent.joinall, [y], raise_error=True)
        x.join()
    test_wait_error.ignore_leakcheck = True

    def test_joinall_exception_order(self):
        # if there're several exceptions raised, the earliest one must be raised by joinall
        def first():
            sleep(0.1)
            raise ExpectedError('first')
        a = gevent.spawn(first)
        b = gevent.spawn(lambda: getcurrent().throw(ExpectedError('second')))
        try:
            gevent.joinall([a, b], raise_error=True)
        except ExpectedError as ex:
            assert 'second' in str(ex), repr(str(ex))
        gevent.joinall([a, b])
    test_joinall_exception_order.ignore_leakcheck = True

    def test_joinall_count_raise_error(self):
        # When joinall is asked not to raise an error, the 'count' param still
        # works.
        def raises_but_ignored():
            raise ExpectedError("count")

        def sleep_forever():
            while True:
                sleep(0.1)

        sleeper = gevent.spawn(sleep_forever)
        raiser = gevent.spawn(raises_but_ignored)

        gevent.joinall([sleeper, raiser], raise_error=False, count=1)
        assert_ready(raiser)
        assert_not_ready(sleeper)

        # Clean up our mess
        sleeper.kill()
        assert_ready(sleeper)

    def test_multiple_listeners_error(self):
        # if there was an error while calling a callback
        # it should not prevent the other listeners from being called
        # also, all of the errors should be logged, check the output
        # manually that they are
        p = gevent.spawn(lambda: 5)
        results = []

        def listener1(*args):
            results.append(10)
            raise ExpectedError('listener1')

        def listener2(*args):
            results.append(20)
            raise ExpectedError('listener2')

        def listener3(*args):
            raise ExpectedError('listener3')

        p.link(listener1)
        p.link(listener2)
        p.link(listener3)
        sleep(DELAY * 10)
        assert results in [[10, 20], [20, 10]], results

        p = gevent.spawn(lambda: getcurrent().throw(ExpectedError('test_multiple_listeners_error')))
        results = []
        p.link(listener1)
        p.link(listener2)
        p.link(listener3)
        sleep(DELAY * 10)
        assert results in [[10, 20], [20, 10]], results

    class Results(object):

        def __init__(self):
            self.results = []

        def listener1(self, p):
            p.unlink(self.listener2)
            self.results.append(5)
            raise ExpectedError('listener1')

        def listener2(self, p):
            p.unlink(self.listener1)
            self.results.append(5)
            raise ExpectedError('listener2')

        def listener3(self, p):
            raise ExpectedError('listener3')

    def _test_multiple_listeners_error_unlink(self, p, link):
        # notification must not happen after unlink even
        # though notification process has been already started
        results = self.Results()

        link(results.listener1)
        link(results.listener2)
        link(results.listener3)
        sleep(DELAY * 10)
        assert results.results == [5], results.results

    def test_multiple_listeners_error_unlink_Greenlet_link(self):
        p = gevent.spawn(lambda: 5)
        self._test_multiple_listeners_error_unlink(p, p.link)
        p.kill()

    def test_multiple_listeners_error_unlink_Greenlet_rawlink(self):
        p = gevent.spawn(lambda: 5)
        self._test_multiple_listeners_error_unlink(p, p.rawlink)

    def test_multiple_listeners_error_unlink_AsyncResult_rawlink(self):
        e = AsyncResult()
        gevent.spawn(e.set, 6)
        self._test_multiple_listeners_error_unlink(e, e.rawlink)

    def test_killing_unlinked(self):
        e = AsyncResult()

        def func():
            try:
                raise ExpectedError('test_killing_unlinked')
            except:
                e.set_exception(sys.exc_info()[1])
                gevent.sleep(0)

        sleep(DELAY)


def dummy_test_func(*args):
    pass


class A(object):

    def method(self):
        pass

hexobj = re.compile('-?0x[0123456789abcdef]+L?', re.I)


class TestStr(greentest.TestCase):

    def test_function(self):
        g = gevent.Greenlet.spawn(dummy_test_func)
        self.assertEqual(hexobj.sub('X', str(g)), '<Greenlet at X: dummy_test_func>')
        assert_not_ready(g)
        g.join()
        assert_ready(g)
        self.assertEqual(hexobj.sub('X', str(g)), '<Greenlet at X: dummy_test_func>')

    def test_method(self):
        g = gevent.Greenlet.spawn(A().method)
        str_g = hexobj.sub('X', str(g))
        str_g = str_g.replace(__name__, 'module')
        self.assertEqual(str_g, '<Greenlet at X: <bound method A.method of <module.A object at X>>>')
        assert_not_ready(g)
        g.join()
        assert_ready(g)
        str_g = hexobj.sub('X', str(g))
        str_g = str_g.replace(__name__, 'module')
        self.assertEqual(str_g, '<Greenlet at X: <bound method A.method of <module.A object at X>>>')


class TestJoin(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        g = gevent.spawn(gevent.sleep, 10)
        try:
            return g.join(timeout=timeout)
        finally:
            g.kill()


class TestGet(greentest.GenericGetTestCase):

    def wait(self, timeout):
        g = gevent.spawn(gevent.sleep, 10)
        try:
            return g.get(timeout=timeout)
        finally:
            g.kill()


class TestJoinAll0(greentest.GenericWaitTestCase):

    g = gevent.Greenlet()

    def wait(self, timeout):
        gevent.joinall([self.g], timeout=timeout)


class TestJoinAll(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        g = gevent.spawn(gevent.sleep, 10)
        try:
            gevent.joinall([g], timeout=timeout)
        finally:
            g.kill()


class TestBasic(greentest.TestCase):

    def test_spawn_non_callable(self):
        self.assertRaises(TypeError, gevent.spawn, 1)
        self.assertRaises(TypeError, gevent.spawn_raw, 1)

        # Not passing the run argument, just the seconds argument
        self.assertRaises(TypeError, gevent.spawn_later, 1)
        # Passing both, but not implemented
        self.assertRaises(TypeError, gevent.spawn_later, 1, 1)

    def test_spawn_raw_kwargs(self):
        value = []

        def f(*args, **kwargs):
            value.append(args)
            value.append(kwargs)

        g = gevent.spawn_raw(f, 1, name='value')
        gevent.sleep(0.01)
        assert not g
        self.assertEqual(value[0], (1,))
        self.assertEqual(value[1], {'name': 'value'})

    def test_simple_exit(self):
        link_test = []

        def func(delay, return_value=4):
            gevent.sleep(delay)
            return return_value

        g = gevent.Greenlet(func, 0.01, return_value=5)
        g.rawlink(link_test.append) # use rawlink to avoid timing issues on Appveyor/Travis (not always successful)
        assert not g, bool(g)
        assert not g.dead
        assert not g.started
        assert not g.ready()
        assert not g.successful()
        assert g.value is None
        assert g.exception is None

        g.start()
        assert g  # changed
        assert not g.dead
        assert g.started  # changed
        assert not g.ready()
        assert not g.successful()
        assert g.value is None
        assert g.exception is None

        gevent.sleep(0.001)
        assert g
        assert not g.dead
        assert g.started
        assert not g.ready()
        assert not g.successful()
        assert g.value is None
        assert g.exception is None
        assert not link_test

        gevent.sleep(0.02)
        assert not g
        assert g.dead
        assert not g.started
        assert g.ready()
        assert g.successful()
        assert g.value == 5
        assert g.exception is None  # not changed
        assert link_test == [g] or greentest.RUNNING_ON_CI, link_test  # changed

    def test_error_exit(self):
        link_test = []

        def func(delay, return_value=4):
            gevent.sleep(delay)
            error = ExpectedError('test_error_exit')
            error.myattr = return_value
            raise error

        g = gevent.Greenlet(func, 0.001, return_value=5)
        # use rawlink to avoid timing issues on Appveyor (not always successful)
        g.rawlink(link_test.append)
        g.start()
        gevent.sleep(0.1)
        assert not g
        assert g.dead
        assert not g.started
        assert g.ready()
        assert not g.successful()
        assert g.value is None  # not changed
        assert g.exception.myattr == 5
        assert link_test == [g] or greentest.RUNNING_ON_APPVEYOR, link_test

    def _assertKilled(self, g):
        assert not g
        assert g.dead
        assert not g.started
        assert g.ready()
        assert g.successful(), (repr(g), g.value, g.exception)
        assert isinstance(g.value, gevent.GreenletExit), (repr(g), g.value, g.exception)
        assert g.exception is None

    def assertKilled(self, g):
        self._assertKilled(g)
        gevent.sleep(0.01)
        self._assertKilled(g)

    def _test_kill(self, g, block):
        g.kill(block=block)
        if not block:
            gevent.sleep(0.01)
        self.assertKilled(g)
        # kill second time must not hurt
        g.kill(block=block)
        self.assertKilled(g)

    def _test_kill_not_started(self, block):
        link_test = []
        result = []
        g = gevent.Greenlet(lambda: result.append(1))
        g.link(lambda x: link_test.append(x))
        self._test_kill(g, block=block)
        assert not result
        assert link_test == [g]

    def test_kill_not_started_block(self):
        self._test_kill_not_started(block=True)

    def test_kill_not_started_noblock(self):
        self._test_kill_not_started(block=False)

    def _test_kill_just_started(self, block):
        result = []
        link_test = []
        g = gevent.Greenlet(lambda: result.append(1))
        g.link(lambda x: link_test.append(x))
        g.start()
        self._test_kill(g, block=block)
        assert not result, result
        assert link_test == [g]

    def test_kill_just_started_block(self):
        self._test_kill_just_started(block=True)

    def test_kill_just_started_noblock(self):
        self._test_kill_just_started(block=False)

    def _test_kill_just_started_later(self, block):
        result = []
        link_test = []
        g = gevent.Greenlet(lambda: result.append(1))
        g.link(lambda x: link_test.append(x))
        g.start_later(1)
        self._test_kill(g, block=block)
        assert not result

    def test_kill_just_started_later_block(self):
        self._test_kill_just_started_later(block=True)

    def test_kill_just_started_later_noblock(self):
        self._test_kill_just_started_later(block=False)

    def _test_kill_running(self, block):
        link_test = []
        g = gevent.spawn(gevent.sleep, 10)
        g.link(lambda x: link_test.append(x))
        self._test_kill(g, block=block)
        gevent.sleep(0.01)
        assert link_test == [g]

    def test_kill_running_block(self):
        self._test_kill_running(block=True)

    def test_kill_running_noblock(self):
        self._test_kill_running(block=False)

    def test_exc_info_no_error(self):
        # Before running
        self.assertFalse(greenlet.Greenlet().exc_info)
        g = greenlet.Greenlet(gevent.sleep)
        g.start()
        g.join()
        self.assertFalse(g.exc_info)


class TestStart(greentest.TestCase):

    def test(self):
        g = gevent.spawn(gevent.sleep, 0.01)
        assert g.started
        assert not g.dead
        g.start()
        assert g.started
        assert not g.dead
        g.join()
        assert not g.started
        assert g.dead
        g.start()
        assert not g.started
        assert g.dead


def assert_ready(g):
    assert g.dead, g
    assert g.ready(), g
    assert not bool(g), g


def assert_not_ready(g):
    assert not g.dead, g
    assert not g.ready(), g


class TestRef(greentest.TestCase):

    def test_init(self):
        self.switch_expected = False
        # in python-dbg mode this will check that Greenlet() does not create any circular refs
        gevent.Greenlet()

    def test_kill_scheduled(self):
        gevent.spawn(gevent.sleep, 10).kill()

    def test_kill_started(self):
        g = gevent.spawn(gevent.sleep, 10)
        try:
            gevent.sleep(0.001)
        finally:
            g.kill()


X = object()

if __name__ == '__main__':
    greentest.main()
