#!/bin/sh
set -e -x
python -mtimeit -r 6 -s'from gevent.lock import Semaphore; s = Semaphore()' 's.release()'
python -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); s.acquire()'
python -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); s.acquire(); s.acquire(); s.acquire(); s.acquire()'
