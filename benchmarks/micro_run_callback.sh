#!/bin/sh
set -e -x
python -mtimeit -r 6 -s'from gevent import run,get_hub; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'run_cb(f)'
python -mtimeit -r 6 -s'from gevent import run,get_hub; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'run_cb(f)' 'run()'
python -mtimeit -r 6 -s'from gevent import run,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(100): run_cb(f)'
python -mtimeit -r 6 -s'from gevent import run,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(100): run_cb(f)' 'run()'
python -mtimeit -r 6 -s'from gevent import run,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(10000): run_cb(f)'
python -mtimeit -r 6 -s'from gevent import run,get_hub; from gevent.hub import xrange; run_cb = get_hub().loop.run_callback; f = lambda : 5' 'for _ in xrange(10000): run_cb(f)' 'run()'


