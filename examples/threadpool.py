from __future__ import print_function
import time
import gevent
from gevent.threadpool import ThreadPool


pool = ThreadPool(3)
start = time.time()
for _ in range(4):
    pool.spawn(time.sleep, 1)
gevent.wait()
delay = time.time() - start
print('Running "time.sleep(1)" 4 times with 3 threads. Should take about 2 seconds: %.3fs' % delay)
