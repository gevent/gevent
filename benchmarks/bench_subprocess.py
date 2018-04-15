# -*- coding: utf-8 -*-
"""
Benchmarks for thread locals.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import perf

from gevent import subprocess as gsubprocess
import subprocess as nsubprocess

N = 10

def _bench_spawn(module, loops, close_fds=True):
    total = 0
    for _ in range(loops):
        t0 = perf.perf_counter()
        procs = [module.Popen('/usr/bin/true', close_fds=close_fds)
                 for _ in range(N)]
        t1 = perf.perf_counter()
        for p in procs:
            p.communicate()
            p.poll()
        total += (t1 - t0)
    return total

def bench_spawn_native(loops, close_fds=True):
    return _bench_spawn(nsubprocess, loops, close_fds)

def bench_spawn_gevent(loops, close_fds=True):
    return _bench_spawn(gsubprocess, loops, close_fds)

def main():
    runner = perf.Runner()

    runner.bench_time_func('spawn native no close_fds',
                           bench_spawn_native,
                           False,
                           inner_loops=N)
    runner.bench_time_func('spawn gevent no close_fds',
                           bench_spawn_gevent,
                           False,
                           inner_loops=N)

    runner.bench_time_func('spawn native close_fds',
                           bench_spawn_native,
                           inner_loops=N)
    runner.bench_time_func('spawn gevent close_fds',
                           bench_spawn_gevent,
                           inner_loops=N)


if __name__ == '__main__':
    main()
