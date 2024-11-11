# -*- coding: utf-8 -*-
"""
Benchmarks for greenlet pool.

"""
import gevent.pool

import bench_threadpool
bench_threadpool.ThreadPool = gevent.pool.Pool

if __name__ == '__main__':
    bench_threadpool.main()
