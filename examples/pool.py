from gevent.pool import Pool
import gevent.monkey
gevent.monkey.patch_all()

import time

pool = Pool(3)
start = time.time()
for _ in xrange(4):
    pool.spawn(time.sleep, 1)
pool.join()
delay = time.time() - start
print 'Running "time.sleep(1)" 4 times with 3 greenlets. Should take about 2 seconds: %.3fs' % delay
