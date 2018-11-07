# A greenlet that's killed with an exception should fail.
import gevent.testing as greentest
import gevent


class ExpectedError(greentest.ExpectedException):
    pass


def f():
    gevent.sleep(999)


class TestKillWithException(greentest.TestCase):

    def test_kill_without_exception(self):
        g = gevent.spawn(f)
        g.kill()
        assert g.successful()
        assert isinstance(g.get(), gevent.GreenletExit)

    def test_kill_with_exception(self):
        # issue-607 pointed this case.
        g = gevent.spawn(f)
        g.kill(ExpectedError)
        assert not g.successful()
        self.assertRaises(ExpectedError, g.get)
        assert g.value is None
        assert isinstance(g.exception, ExpectedError)

    def test_kill_with_exception_after_started(self):
        g = gevent.spawn(f)
        g.join(0)
        g.kill(ExpectedError)
        assert not g.successful()
        self.assertRaises(ExpectedError, g.get)
        assert g.value is None
        assert isinstance(g.exception, ExpectedError)


if __name__ == '__main__':
    greentest.main()
