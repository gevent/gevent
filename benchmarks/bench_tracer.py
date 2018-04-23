# -*- coding: utf-8 -*-
"""
Benchmarks for gevent.queue

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib

import perf

import greenlet
import gevent
from gevent import _tracer as monitor

N = 1000

@contextlib.contextmanager
def tracer(cls, *args):
    inst = cls(*args)
    try:
        yield
    finally:
        inst.kill()

def _run(loops):

    duration = 0

    for _ in range(loops):

        g1 = None
        def switch():
            parent = gevent.getcurrent().parent
            for _ in range(N):
                parent.switch()

        g1 = gevent.Greenlet(switch)
        g1.parent = gevent.getcurrent()

        t1 = perf.perf_counter()
        for _ in range(N):
            g1.switch()

        t2 = perf.perf_counter()

        duration += t2 - t1
    return duration


def bench_no_trace(loops):
    return _run(loops)

def bench_trivial_tracer(loops):

    def trivial(_event, _args):
        return

    greenlet.settrace(trivial)
    try:
        return _run(loops)
    finally:
        greenlet.settrace(None)


def bench_monitor_tracer(loops):
    with tracer(monitor.GreenletTracer):
        return _run(loops)


def bench_hub_switch_tracer(loops):
    # use current as the hub, since tracer fires
    # when we switch into that greenlet
    with tracer(monitor.HubSwitchTracer, gevent.getcurrent(), 1):
        return _run(loops)

def bench_max_switch_tracer(loops):
    # use object() as the hub, since tracer fires
    # when switch into something that's *not* the hub
    with tracer(monitor.MaxSwitchTracer, object, 1):
        return _run(loops)

def main():
    runner = perf.Runner()

    runner.bench_time_func(
        "no tracer",
        bench_no_trace,
        inner_loops=N
    )

    runner.bench_time_func(
        "trivial tracer",
        bench_trivial_tracer,
        inner_loops=N
    )

    runner.bench_time_func(
        "monitor tracer",
        bench_monitor_tracer,
        inner_loops=N
    )

    runner.bench_time_func(
        "max switch tracer",
        bench_max_switch_tracer,
        inner_loops=N
    )

    runner.bench_time_func(
        "hub switch tracer",
        bench_hub_switch_tracer,
        inner_loops=N
    )


if __name__ == '__main__':
    main()
