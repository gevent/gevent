#!/usr/bin/python
# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

"""Spawn multiple workers and wait for them to complete"""
from __future__ import print_function
import sys

urls = ['http://www.google.com', 'http://www.yandex.ru', 'http://www.python.org']

import gevent
from gevent import monkey

# patches stdlib (including socket and ssl modules) to cooperate with other greenlets
monkey.patch_all()


if sys.version_info[0] == 3:
    from urllib.request import urlopen
else:
    from urllib2 import urlopen


def print_head(url):
    print('Starting %s' % url)
    data = urlopen(url).read()
    print('%s: %s bytes: %r' % (url, len(data), data[:50]))

jobs = [gevent.spawn(print_head, url) for url in urls]

gevent.wait(jobs)
