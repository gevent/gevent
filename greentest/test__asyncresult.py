import greentest
import gevent
from gevent.event import AsyncResult

DELAY = 0.01


class TestLink_Signal(greentest.TestCase):

    def test_put(self):
        g = gevent.spawn(lambda : 1)
        s1, s2, s3 = AsyncResult(), AsyncResult(), AsyncResult()
        g.link(s1)
        g.link_value(s2)
        g.link_exception(s3)
        assert s1.get() == 1
        assert s2.get() == 1
        assert gevent.with_timeout(DELAY, s3.get, timeout_value=X) is X

    def test_put_exception(self):
        g = gevent.spawn(lambda : 1/0)
        s1, s2, s3 = AsyncResult(), AsyncResult(), AsyncResult()
        g.link(s1)
        g.link_value(s2)
        g.link_exception(s3)
        self.assertRaises(ZeroDivisionError, s1.get)
        assert gevent.with_timeout(DELAY, s2.get, timeout_value=X) is X
        self.assertRaises(ZeroDivisionError, s3.get)

X = object()

if __name__=='__main__':
    greentest.main()
