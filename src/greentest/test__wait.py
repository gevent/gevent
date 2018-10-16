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

    def test_wait_unique(self):
        sem1 = Semaphore()
        sem2 = Semaphore()

        def release():
            for i in range(2):
                sem1.release()
                gevent.idle()
            sem2.release()

        glet = gevent.spawn(release)
        waited_objs = set(gevent.iwait((sem1, sem2)))
        self.assertEqual(waited_objs, set([sem1, sem2]))
        glet.kill()
        glet.get()


if __name__ == '__main__':
        greentest.main()
