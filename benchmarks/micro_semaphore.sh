#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}
$PYTHON -mtimeit -r 6 -s'from gevent.lock import Semaphore; s = Semaphore()' 's.release()'
$PYTHON -mtimeit -r 6 -s'from gevent.lock import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); s.acquire()'
$PYTHON -mtimeit -r 6 -s'from gevent.lock import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); s.acquire(); s.acquire(); s.acquire(); s.acquire()'
