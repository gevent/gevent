#!/usr/bin/env python
"""An example on how to communicate with a subprocess.

Written by Marcus Cavanaugh.
See http://groups.google.com/group/gevent/browse_thread/thread/7fca7230db0509f6
where it was first posted.
"""

import gevent
from gevent import socket

import subprocess
import errno
import sys
import os
import fcntl


def popen_communicate(args, data=''):
    """Communicate with the process non-blockingly."""
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    fcntl.fcntl(p.stdin, fcntl.F_SETFL, os.O_NONBLOCK)  # make the file nonblocking
    fcntl.fcntl(p.stdout, fcntl.F_SETFL, os.O_NONBLOCK)  # make the file nonblocking

    bytes_total = len(data)
    bytes_written = 0
    while bytes_written < bytes_total:
        try:
            # p.stdin.write() doesn't return anything, so use os.write.
            bytes_written += os.write(p.stdin.fileno(), data[bytes_written:])
        except IOError, ex:
            if ex[0] != errno.EAGAIN:
                raise
            sys.exc_clear()
        socket.wait_write(p.stdin.fileno())

    p.stdin.close()

    chunks = []

    while True:
        try:
            chunk = p.stdout.read(4096)
            if not chunk:
                break
            chunks.append(chunk)
        except IOError, ex:
            if ex[0] != errno.EAGAIN:
                raise
            sys.exc_clear()
        socket.wait_read(p.stdout.fileno())

    p.stdout.close()
    return ''.join(chunks)


if __name__ == '__main__':
    # run 2 jobs in parallel
    job1 = gevent.spawn(popen_communicate, 'finger')
    job2 = gevent.spawn(popen_communicate, 'netstat')

    # wait for them to complete. stop waiting after 2 seconds
    gevent.joinall([job1, job2], timeout=2)

    # print the results (if available)
    if job1.ready():
        print 'finger: %s bytes: %s' % (len(job1.value), repr(job1.value)[:50])
    else:
        print 'finger: job is still running'
    if job2.ready():
        print 'netstat: %s bytes: %s' % (len(job2.value), repr(job2.value)[:50])
    else:
        print 'netstat: job is still running'
