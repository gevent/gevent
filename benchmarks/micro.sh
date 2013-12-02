#!/bin/sh
set -e -x
python -c 'import gevent.core; from __future__ import print_function; print(gevent.__version__, gevent.core.get_version(), getattr(gevent.core, "get_method", lambda: "n/a")(), getattr(gevent, "get_hub", lambda: "n/a")())'
python -mtimeit -r 6 -s'obj = Exception(); obj.x=5' 'obj.x'
python -mtimeit -r 6 -s'from gevent import get_hub; get_hub()' 'get_hub()'
python -mtimeit -r 6 -s'from gevent import getcurrent' 'getcurrent()'

python -mtimeit -r 6 -s'from gevent.lock import Semaphore; s = Semaphore()' 's.release()'
python -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); s.acquire()'
python -mtimeit -r 6 -s'from gevent.coros import Semaphore; from gevent import spawn_raw; s = Semaphore(0)' 'spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); spawn_raw(s.release); s.acquire(); s.acquire(); s.acquire(); s.acquire()'

python -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f)'
python -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f).join()'
python -mtimeit -r 6 -s'from gevent import spawn, run; from gevent.hub import xrange; f = lambda : 5' 'for _ in xrange(10000): spawn(f)' 'run()'
python -mtimeit -r 6 -s'from gevent import spawn_raw; f = lambda : 5' 'spawn_raw(f)'

python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'

benchmarks/micro_run_callback.sh
benchmarks/micro_semaphore.sh
benchmarks/micro_sleep.sh
benchmarks/micro_greenlet_link.sh
