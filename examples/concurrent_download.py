# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

"""Spawn multiple workers and wait for them to complete"""

urls = ['http://www.google.com', 'http://www.yandex.ru', 'http://www.python.org']

from gevent import monkey
monkey.patch_socket() # patches regular socket to yield to other greenlets

import urllib2
from gevent.pool import Pool

# Pool accepts one optional argument - maximum number of concurrent
# coroutines that can be active at any given moment.
# Try passing 1 or 2 here to see the effect.
pool = Pool()

def print_head(url):
    print 'Starting %s' % url
    data = urllib2.urlopen(url).read()
    print '%s: %s bytes: %r' % (url, len(data), data[:50])

for url in urls:
    pool.spawn(print_head, url)

pool.join()

