#!/bin/sh
set -e
set -x
python -c 'import gevent.core; print gevent.__version__, gevent.core.get_version(), getattr(gevent.core, "get_method", lambda: "n/a")(), getattr(gevent, "get_hub", lambda: "n/a")()'
python -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f)'
python -mtimeit -r 6 -s'from gevent import spawn; f = lambda : 5' 'spawn(f).join()'
python -mtimeit -r 6 -s'from gevent import spawn_raw; f = lambda : 5' 'spawn_raw(f)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda: 5' 'for _ in xrange(1000): g.link(l)'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(1000): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(10000): g.link(l);' 'g.join()'
python -mtimeit -r 6 -s'from gevent import spawn; g = spawn(lambda: 5); l = lambda *args: 5' 'for _ in xrange(100000): g.link(l);' 'g.join()'
