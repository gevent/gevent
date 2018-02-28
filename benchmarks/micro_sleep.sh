#!/bin/sh
set -e -x
PYTHON=${PYTHON:=python}

$PYTHON -m perf timeit -s 'from gevent import sleep; f = lambda : 5' 'sleep(0)'
$PYTHON -m perf timeit -s 'from gevent import sleep; f = lambda : 5' 'sleep(0.00001)'
$PYTHON -m perf timeit -s 'from gevent import sleep; f = lambda : 5' 'sleep(0.0001)'
$PYTHON -m perf timeit -s 'from gevent import sleep; f = lambda : 5' 'sleep(0.001)'
