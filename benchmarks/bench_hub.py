# -*- coding: utf-8 -*-
"""
Benchmarks for hub primitive operations.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import perf
from perf import perf_counter

import gevent
from greenlet import greenlet
from greenlet import getcurrent


N = 1000

def bench_switch():

    class Parent(type(gevent.get_hub())):
        def run(self):
            parent = self.parent
            for _ in range(N):
                parent.switch()

    def child():
        parent = getcurrent().parent
        # Back to the hub, which in turn goes
        # back to the main greenlet
        for _ in range(N):
            parent.switch()

    hub = Parent(None, None)
    child_greenlet = greenlet(child, hub)
    for _ in range(N):
        child_greenlet.switch()

def bench_wait_ready():

    class Watcher(object):
        def start(self, cb, obj):
            # Immediately switch back to the waiter, mark as ready
            cb(obj)

        def stop(self):
            pass

    watcher = Watcher()
    hub = gevent.get_hub()

    for _ in range(1000):
        hub.wait(watcher)

def bench_cancel_wait():

    class Watcher(object):
        active = True
        callback = object()

        def close(self):
            pass

    watcher = Watcher()
    hub = gevent.get_hub()
    loop = hub.loop

    for _ in range(1000):
        # Schedule all the callbacks.
        hub.cancel_wait(watcher, None, True)

    # Run them!
    for cb in loop._callbacks:
        if cb.callback:
            cb.callback(*cb.args)
            cb.stop() # so the real loop won't do it

    # destroy the loop so we don't keep building these functions
    # up
    hub.destroy(True)

def bench_wait_func_ready():
    from gevent.hub import wait
    class ToWatch(object):
        def rawlink(self, cb):
            cb(self)

    watched_objects = [ToWatch() for _ in range(N)]

    t0 = perf_counter()

    wait(watched_objects)

    return perf_counter() - t0

def main():

    runner = perf.Runner()

    runner.bench_func('multiple wait ready',
                      bench_wait_func_ready,
                      inner_loops=N)

    runner.bench_func('wait ready',
                      bench_wait_ready,
                      inner_loops=N)

    runner.bench_func('cancel wait',
                      bench_cancel_wait,
                      inner_loops=N)

    runner.bench_func('switch',
                      bench_switch,
                      inner_loops=N)

if __name__ == '__main__':
    main()
