#!/usr/bin/env python
import gevent
from gevent import subprocess


# run 2 jobs in parallel
p1 = subprocess.Popen(['uname'], stdout=subprocess.PIPE)
p2 = subprocess.Popen(['ls'], stdout=subprocess.PIPE)

job1 = gevent.spawn(p1.stdout.read)
job2 = gevent.spawn(p2.stdout.read)

# wait for them to complete. stop waiting after 2 seconds
gevent.joinall([job1, job2], timeout=2)

# print the results (if available)
if job1.ready():
    print ('uname: %s bytes: %s' % (len(job1.value or ''), repr(job1.value)[:50]))
else:
    print ('uname: job is still running')
if job2.ready():
    print ('ls: %s bytes: %s' % (len(job2.value or ''), repr(job2.value)[:50]))
else:
    print ('ls: job is still running')
