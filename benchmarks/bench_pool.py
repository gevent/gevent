# -*- coding: utf-8 -*-
"""
Benchmarks for greenlet pool.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gevent.pool

import bench_threadpool
bench_threadpool.ThreadPool = gevent.pool.Pool

if __name__ == '__main__':
    bench_threadpool.main()
