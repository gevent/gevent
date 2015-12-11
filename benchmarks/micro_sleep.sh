#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}
$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0)'
$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.00001)'
$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'
$PYTHON -mtimeit -r 6 -s'from gevent import sleep; f = lambda : 5' 'sleep(0.001)'
