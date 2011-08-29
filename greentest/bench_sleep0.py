from time import time
from gevent import sleep
import os


N = 10


while True:
    start = time()
    user_time, system_time = os.times()[:2]
    for _ in xrange(N):
        sleep(0)
    user_time_x, system_time_x = os.times()[:2]
    delta = time() - start
    if delta > 0.2:
        break
    N *= 10
user_time_x -= user_time
system_time_x -= system_time
ms = 1000000. / N
print 'N=%s delta=%s utime=%s stime=%s' % (N, delta, user_time_x, system_time_x)
print ('sleep(0): %.1f, utime: %.1f, stime: %.1f (microseconds)' % (delta * ms, user_time_x * ms, system_time_x * ms))
