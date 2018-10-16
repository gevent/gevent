import gevent
import greentest
from gevent.lock import Semaphore


class TestWaiting(greentest.TestCase):
    def test_wait_noiter(self):
        """Test that gevent.iwait returns objects which can be iterated upon
        without additional calls to iter()"""

        sem1 = Semaphore()
        sem2 = Semaphore()

        gevent.spawn(sem1.release)
        ready = next(gevent.iwait((sem1, sem2)))
        self.assertEqual(sem1, ready)
