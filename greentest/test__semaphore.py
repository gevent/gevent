import greentest
from gevent.coros import Semaphore


class TestTimeoutAcquire(greentest.TestCase):

    # issue 39
    def test_acquire_returns_false_after_timeout(self):
        s = Semaphore(value=0)
        result = s.acquire(timeout=0.01)
        assert result is False, repr(result)


if __name__ == '__main__':
    greentest.main()
