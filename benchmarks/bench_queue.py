# -*- coding: utf-8 -*-
"""
Benchmarks for gevent.queue

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import perf

import gevent
from gevent import queue

N = 1000

def _b_no_block(q):
    for i in range(N):
        q.put(i)

    for i in range(N):
        j = q.get()
        assert i == j, (i, j)

def bench_unbounded_queue_noblock(kind=queue.UnboundQueue):
    _b_no_block(kind())

def bench_bounded_queue_noblock(kind=queue.Queue):
    _b_no_block(kind(N + 1))

def bench_bounded_queue_block(kind=queue.Queue, hub=False):

    q = kind(1)

    def get():
        for i in range(N):
            j = q.get()
            assert i == j
        return "Finished"

    # Run putters in the main greenlet
    g = gevent.spawn(get)
    if not hub:
        for i in range(N):
            q.put(i)
    else:
        # putters in the hub
        def put():
            assert gevent.getcurrent() is gevent.get_hub()
            for i in range(N):
                q.put(i)
        h = gevent.get_hub()
        h.loop.run_callback(put)
        h.join()
    g.join()
    assert g.value == 'Finished'

def main():
    runner = perf.Runner()

    runner.bench_func('bench_unbounded_queue_noblock',
                      bench_unbounded_queue_noblock,
                      inner_loops=N)

    runner.bench_func('bench_bounded_queue_noblock',
                      bench_bounded_queue_noblock,
                      inner_loops=N)

    runner.bench_func('bench_bounded_queue_block',
                      bench_bounded_queue_block,
                      inner_loops=N)

    runner.bench_func('bench_channel',
                      bench_bounded_queue_block,
                      queue.Channel,
                      inner_loops=N)

    runner.bench_func('bench_bounded_queue_block_hub',
                      bench_bounded_queue_block,
                      queue.Queue, True,
                      inner_loops=N)

    runner.bench_func('bench_channel_hub',
                      bench_bounded_queue_block,
                      queue.Channel, True,
                      inner_loops=N)

    runner.bench_func('bench_unbounded_priority_queue_noblock',
                      bench_unbounded_queue_noblock,
                      queue.PriorityQueue,
                      inner_loops=N)

    runner.bench_func('bench_bounded_priority_queue_noblock',
                      bench_bounded_queue_noblock,
                      queue.PriorityQueue,
                      inner_loops=N)



if __name__ == '__main__':
    main()
