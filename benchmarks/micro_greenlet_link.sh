#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda: 5' 'for _ in xrange(1000): g.link(l)'
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10): g.link(l);' 'g.join()'
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100): g.link(l);' 'g.join()'
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(1000): g.link(l);' 'g.join()'
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10000): g.link(l);' 'g.join()'
$PYTHON -mperf timeit  -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100000): g.link(l);' 'g.join()'
