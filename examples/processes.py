#!/usr/bin/env python
from __future__ import print_function
import gevent
from gevent import subprocess


# run 2 jobs in parallel
p1 = subprocess.Popen(['uname'], stdout=subprocess.PIPE)
p2 = subprocess.Popen(['ls'], stdout=subprocess.PIPE)

gevent.wait([p1, p2], timeout=2)

# print the results (if available)
if p1.poll() is not None:
    print('uname: %r' % p1.stdout.read())
else:
    print('uname: job is still running')
if p2.poll() is not None:
    print('ls: %r' % p2.stdout.read())
else:
    print('ls: job is still running')
