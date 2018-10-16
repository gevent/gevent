import gevent
import greentest
from gevent.lock import Semaphore


class TestWaiting(greentest.TestCase):
    def test_wait_noiter(self):
        sem1 = Semaphore()
        sem2 = Semaphore()

        gevent.spawn(sem1.release)
        ready = next(gevent.iwait((sem1, sem2)))
        self.assertEqual(sem1, ready)


if __name__ == '__main__':
        greentest.main()
