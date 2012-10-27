#!/bin/sh
set -e -x
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.00001)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'
python -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.001)'
