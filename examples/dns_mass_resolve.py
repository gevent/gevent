#!/usr/bin/python
"""Resolve hostnames concurrently, exit after 2 seconds.

Under the hood, this might use an asynchronous resolver based on
c-ares (the default) or thread-pool-based resolver.

You can choose between resolvers using GEVENT_RESOLVER environment
variable. To enable threading resolver:

    GEVENT_RESOLVER=thread python dns_mass_resolve.py
"""
from __future__ import print_function
import gevent
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
            print('%s = %s' % (url, ip))
        except socket.gaierror as ex:
            print('%s failed with %s' % (url, ex))
    finally:
        finished += 1

with gevent.Timeout(2, False):
    for x in range(10, 10 + N):
        pool.spawn(job, '%s.com' % x)
    pool.join()

print('finished within 2 seconds: %s/%s' % (finished, N))
