#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}
$PYTHON -c 'from __future__ import print_function; import gevent.core; print(gevent.__version__, gevent.core.get_version(), getattr(gevent.core, "get_method", lambda: "n/a")(), getattr(gevent, "get_hub", lambda: "n/a")())'
$PYTHON -mtimeit -r 6 -s'obj = Exception(); obj.x=5' 'obj.x'
$PYTHON -mtimeit -r 6 -s'from gevent import get_hub; get_hub()' 'get_hub()'
$PYTHON -mtimeit -r 6 -s'from gevent import getcurrent' 'getcurrent()'

$PYTHON -mtimeit -r 6 -s'from gevent.lock import Semaphore; s = Semaphore()' 's.release()'
$PYTHON -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); s.acquire()'
$PYTHON -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); s.acquire(); s.acquire(); s.acquire(); s.acquire()'

$PYTHON -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f)'
$PYTHON -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f).join()'
$PYTHON -mtimeit -r 6 -s'from gevent import spawn, wait; from gevent.hub import xrange; f = lambda : 5' 'for _ in xrange(10000): spawn(f)' 'wait()'
$PYTHON -mtimeit -r 6 -s'from gevent import spawn_raw; f = lambda : 5' 'spawn_raw(f)'

$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0)'
$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'

benchmarks/micro_run_callback.sh
benchmarks/micro_semaphore.sh
benchmarks/micro_sleep.sh
benchmarks/micro_greenlet_link.sh
