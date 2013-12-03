#!/bin/sh
set -e -x
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda: 5' 'for _ in xrange(1000): g.link(l)'
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(1000): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10000): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; from gevent.hub import xrange; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100000): g.link(l);' 'g.join()'
