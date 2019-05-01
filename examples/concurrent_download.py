#!/usr/bin/python
# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.
# gevent-test-requires-resource: network
"""Spawn multiple workers and wait for them to complete"""
from __future__ import print_function
import gevent
from gevent import monkey

# patches stdlib (including socket and ssl modules) to cooperate with other greenlets
monkey.patch_all()

import requests

# Note that we're using HTTPS, so
# this demonstrates that SSL works.
urls = [
    'https://www.google.com/',
    'https://www.apple.com/',
    'https://www.python.org/'
]



def print_head(url):
    print('Starting %s' % url)
    data = requests.get(url).text
    print('%s: %s bytes: %r' % (url, len(data), data[:50]))

jobs = [gevent.spawn(print_head, _url) for _url in urls]

gevent.wait(jobs)
