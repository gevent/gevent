def aaa(lock, e1, e2):
    print("aaa")
    e1.set()
    with lock:
        e2.wait()


def bbb(lock, e1, e2):
    print("bbb")
    e1.wait()
    e2.set()
    with lock:
        pass


import threading
test_lock = threading.RLock()
import gevent
import gevent.monkey
gevent.monkey.patch_all()

e1, e2 = threading.Event(), threading.Event()
a = gevent.spawn(aaa, test_lock, e1, e2)
b = gevent.spawn(bbb, test_lock, e1, e2)
a.join()
b.join()
