from time import time
from gevent import sleep

N = 10000


start = time()
for _ in xrange(N):
    sleep(0)
delta = time() - start
print 'sleep(0): %.1f microseconds' % (delta * 1000000.0 / N)
