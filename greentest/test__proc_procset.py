import time
import greentest
import gevent
from gevent import proc

DELAY = 0.01

class Undead(object):

    def __init__(self):
        self.shot_count = 0

    def __call__(self):
        while True:
            try:
                gevent.sleep(1)
            except:
                self.shot_count += 1

class Test(greentest.TestCase):

    def test_basic(self):
        DELAY = 0.05
        s = proc.ProcSet()
        s.spawn(gevent.sleep, DELAY)
        s.spawn(gevent.sleep, DELAY*2.)
        assert len(s)==2, s
        gevent.sleep(DELAY*3./2.)
        assert len(s)==1, s
        gevent.sleep(DELAY)
        assert not s, s

    def test_waitall(self):
        s = proc.ProcSet()
        s.spawn(gevent.sleep, DELAY)
        s.spawn(gevent.sleep, DELAY*2)
        assert len(s)==2, s
        start = time.time()
        s.waitall()
        delta = time.time() - start
        assert not s, s
        assert len(s)==0, s
        assert DELAY*2 < delta < DELAY*2.5, delta

    def test_killall_wait(self):
        s = proc.ProcSet()
        s.spawn(gevent.sleep, DELAY)
        s.spawn(gevent.sleep, DELAY*2)
        assert len(s)==2, s
        start = time.time()
        s.killall(block=True)
        assert not s, s
        assert len(s)==0, s
        delta = time.time() - start
        assert delta < DELAY*0.5, delta

    def test_killall_nowait(self):
        s = proc.ProcSet()
        s.spawn(gevent.sleep, DELAY)
        s.spawn(gevent.sleep, DELAY*2)
        assert len(s)==2, s
        s.killall()
        assert len(s)==2, s
        gevent.sleep(0)
        assert not s, s
        assert len(s)==0, s

    def test_kill_fires_once(self):
        u1 = Undead()
        u2 = Undead()
        p1 = proc.spawn(u1)
        p2 = proc.spawn(u2)
        s = proc.ProcSet([p1, p2])
        assert u1.shot_count == 0, u1.shot_count
        s.kill(p1)
        assert u1.shot_count == 0, u1.shot_count
        gevent.sleep(0)
        assert u1.shot_count == 1, u1.shot_count
        s.kill(p1)
        assert u1.shot_count == 1, u1.shot_count
        s.kill(p1)
        assert u2.shot_count == 0, u2.shot_count
        s.killall()
        s.killall()
        s.killall()
        assert u1.shot_count == 1, u1.shot_count
        assert u2.shot_count == 0, u2.shot_count
        gevent.sleep(DELAY)
        assert u1.shot_count == 1, u1.shot_count
        assert u2.shot_count == 1, u2.shot_count
        X = object()
        assert X is gevent.with_timeout(DELAY, s.killall, block=True, timeout_value=X)

    def test_killall_subclass(self):
        p1 = Proc1.spawn(lambda : 1/0)
        p2 = Proc1.spawn(lambda : gevent.sleep(10))
        s = proc.ProcSet([p1, p2])
        s.killall(block=True)


class Proc1(proc.Proc):
    pass


if __name__=='__main__':
    greentest.main()

