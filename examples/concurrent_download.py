#!/usr/bin/python
# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

"""Spawn multiple workers and wait for them to complete"""

urls = ['http://www.google.com', 'http://www.yandex.ru', 'http://www.python.org']

import gevent
from gevent import monkey

# patches stdlib (including socket and ssl modules) to cooperate with other greenlets
monkey.patch_all()

import urllib2


def print_head(url):
    print ('Starting %s' % url)
    data = urllib2.urlopen(url).read()
    print ('%s: %s bytes: %r' % (url, len(data), data[:50]))

jobs = [gevent.spawn(print_head, url) for url in urls]

gevent.wait(jobs)
