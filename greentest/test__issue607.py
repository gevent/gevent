# A greenlet that's killed with an exception should fail.
import greentest
import gevent


class ExpectedError(greentest.ExpectedException):
    pass


class TestKillWithException(greentest.TestCase):

    def test_kill_without_exception(self):
        g = gevent.spawn()
        g.kill()
        assert g.successful()
        assert isinstance(g.get(), gevent.GreenletExit)

    def test_kill_with_exception(self):
        g = gevent.spawn()
        g.kill(ExpectedError)
        assert not g.successful()
        self.assertRaises(ExpectedError, g.get)
        assert g.value is None
        assert isinstance(g.exception, ExpectedError)


if __name__ == '__main__':
    greentest.main()
