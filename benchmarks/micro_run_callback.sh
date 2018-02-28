#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}
$PYTHON -mperf timeit  -s'from gevent import get_hub; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'run_cb(f)'
$PYTHON -mperf timeit  -s'from gevent import wait,get_hub; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'run_cb(f)' 'wait()'
$PYTHON -mperf timeit  -s'from gevent import get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(100): run_cb(f)'
$PYTHON -mperf timeit  -s'from gevent import wait,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(100): run_cb(f)' 'wait()'
$PYTHON -mperf timeit  -s'from gevent import get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(10000): run_cb(f)'
$PYTHON -mperf timeit  -s'from gevent import wait,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(10000): run_cb(f)' 'wait()'
