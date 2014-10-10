import greentest
import gevent
from gevent.hub import get_hub

DELAY = 0.01


class TestDirectRaise(greentest.TestCase):
    switch_expected = False

    def test_direct_raise_class(self):
        try:
            raise gevent.Timeout
        except gevent.Timeout as t:
            assert not t.pending, repr(t)

    def test_direct_raise_instance(self):
        timeout = gevent.Timeout()
        try:
            raise timeout
        except gevent.Timeout as t:
            assert timeout is t, (timeout, t)
            assert not t.pending, repr(t)


class Test(greentest.TestCase):

    def _test(self, timeout):
        try:
            get_hub().switch()
            raise AssertionError('Must raise Timeout')
        except gevent.Timeout as ex:
            if ex is not timeout:
                raise

    def test(self):
        timeout = gevent.Timeout(0.01)
        timeout.start()
        self._test(timeout)
        timeout.start()
        self._test(timeout)

    def test_false(self):
        timeout = gevent.Timeout(0.01, False)
        timeout.start()
        self._test(timeout)
        timeout.start()
        self._test(timeout)

    def test_cancel(self):
        timeout = gevent.Timeout(0.01)
        timeout.start()
        timeout.cancel()
        gevent.sleep(0.02)
        assert not timeout.pending, timeout

    def test_with_timeout(self):
        self.assertRaises(gevent.Timeout, gevent.with_timeout, DELAY, gevent.sleep, DELAY * 2)
        X = object()
        r = gevent.with_timeout(DELAY, gevent.sleep, DELAY * 2, timeout_value=X)
        assert r is X, (r, X)
        r = gevent.with_timeout(DELAY * 2, gevent.sleep, DELAY, timeout_value=X)
        assert r is None, r


if __name__ == '__main__':
    greentest.main()
