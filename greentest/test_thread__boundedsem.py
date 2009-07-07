"""Test that a BoundedSemaphore with a very high bound is as good as an unbounded one"""
from gevent import coros
from gevent import thread

def allocate_lock():
    return coros.BoundedSemaphore(1, 9999)

thread.allocate_lock = allocate_lock
thread.LockType = coros.BoundedSemaphore

execfile('test_thread.py')

import thread
assert thread.allocate_lock is allocate_lock, (thread.allocate_lock, allocate_lock)
