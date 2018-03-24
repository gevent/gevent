# -*- coding: utf-8 -*-
"""
Benchmarks for thread pool.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import perf

from gevent.threadpool import ThreadPool

try:
    xrange = xrange
except NameError:
    xrange = range

def noop():
    "Does nothing"

def identity(i):
    return i

PAR_COUNT = 5
N = 20

def bench_apply(loops):
    pool = ThreadPool(1)
    t0 = perf.perf_counter()

    for _ in xrange(loops):
        for _ in xrange(N):
            pool.apply(noop)

    pool.join()
    pool.kill()
    return perf.perf_counter() - t0

def bench_spawn_wait(loops):
    pool = ThreadPool(1)

    t0 = perf.perf_counter()

    for _ in xrange(loops):
        for _ in xrange(N):
            r = pool.spawn(noop)
            r.get()

    pool.join()
    pool.kill()
    return perf.perf_counter() - t0

def _map(pool, pool_func, loops):
    data = [1] * N
    t0 = perf.perf_counter()

    # Must collect for imap to finish
    for _ in xrange(loops):
        list(pool_func(identity, data))

    pool.join()
    pool.kill()
    return perf.perf_counter() - t0

def _ppool():
    pool = ThreadPool(PAR_COUNT)
    pool.size = PAR_COUNT
    return pool

def bench_map_seq(loops):
    pool = ThreadPool(1)
    return _map(pool, pool.map, loops)

def bench_map_par(loops):
    pool = _ppool()
    return _map(pool, pool.map, loops)

def bench_imap_seq(loops):
    pool = ThreadPool(1)
    return _map(pool, pool.imap, loops)

def bench_imap_par(loops):
    pool = _ppool()
    return _map(pool, pool.imap, loops)

def bench_imap_un_seq(loops):
    pool = ThreadPool(1)
    return _map(pool, pool.imap_unordered, loops)

def bench_imap_un_par(loops):
    pool = _ppool()
    return _map(pool, pool.imap_unordered, loops)

def main():
    runner = perf.Runner()

    runner.bench_time_func('imap_unordered_seq',
                           bench_imap_un_seq)

    runner.bench_time_func('imap_unordered_par',
                           bench_imap_un_par)

    runner.bench_time_func('imap_seq',
                           bench_imap_seq)

    runner.bench_time_func('imap_par',
                           bench_imap_par)

    runner.bench_time_func('map_seq',
                           bench_map_seq)

    runner.bench_time_func('map_par',
                           bench_map_par)

    runner.bench_time_func('apply',
                           bench_apply)

    runner.bench_time_func('spawn',
                           bench_spawn_wait)


if __name__ == '__main__':
    main()
