import threading
import gevent.monkey
gevent.monkey.patch_all()
import gevent

assert threading._sleep is gevent.sleep, threading._sleep
