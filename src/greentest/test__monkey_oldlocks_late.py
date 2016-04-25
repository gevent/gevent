def aaa(lock, e1, e2):
    e1.set()
    with lock:
        e2.wait()


def bbb(lock, e1, e2):
    e1.wait()
    e2.set()
    with lock:
        pass


import threading
import gevent
import gevent.monkey
gevent.monkey.patch_all()
test_lock = threading.RLock()

e1, e2 = threading.Event(), threading.Event()
a = gevent.spawn(aaa, test_lock, e1, e2)
b = gevent.spawn(bbb, test_lock, e1, e2)
a.join()
b.join()
