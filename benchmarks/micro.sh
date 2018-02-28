#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}

$PYTHON -c 'from __future__ import print_function; import gevent.core; print(gevent.__version__, gevent.core.get_version(), getattr(gevent.core, "get_method", lambda: "n/a")(), getattr(gevent, "get_hub", lambda: "n/a")())'
$PYTHON -mperf timeit  -s'obj = Exception(); obj.x=5' 'obj.x'
$PYTHON -mperf timeit  -s'from gevent import get_hub; get_hub()' 'get_hub()'
$PYTHON -mperf timeit  -s'from gevent import getcurrent' 'getcurrent()'


$PYTHON -mperf timeit  -s'from gevent import spawn; f = lambda : 5' 'spawn(f)'
$PYTHON -mperf timeit  -s'from gevent import spawn; f = lambda : 5' 'spawn(f).join()'
$PYTHON -mperf timeit  -s'from gevent import spawn, wait; from gevent.hub import xrange; f = lambda : 5' 'for _ in xrange(10000): spawn(f)' 'wait()'
$PYTHON -mperf timeit  -s'from gevent import spawn_raw; f = lambda : 5' 'spawn_raw(f)'


benchmarks/micro_run_callback.sh
benchmarks/micro_semaphore.sh
benchmarks/micro_sleep.sh
benchmarks/micro_greenlet_link.sh
