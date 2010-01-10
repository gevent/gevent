#!/usr/bin/python
"""Resolve hostnames concurrently, exit after 2 seconds.

Note, that gevent.socket.gethostname uses libevent-dns under the hood
and yields the control to other greenlets until the result is ready.
This script splits the job between a number of greenlets to get the
results faster.
"""

from gevent import socket
from gevent.pool import Pool

N = 1000

# limit ourselves to max 10 simultaneous outstanding requests
pool = Pool(10)

finished = 0

def job(url):
    global finished
    try:
        try:
            ip = socket.gethostbyname(url)
            print '%s = %s' % (url, ip)
        except socket.gaierror, ex:
            print '%s failed with %s' % (url, ex)
    finally:
        finished += 1

for x in xrange(10, N):
    pool.spawn(job, '%s.com' % x)

pool.join(timeout=2)
print 'finished within 2 seconds: %s/%s' % (finished, N)
