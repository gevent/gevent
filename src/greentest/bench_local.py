# -*- coding: utf-8 -*-
"""
Benchmarks for thread locals.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import perf

from gevent.local import local as glocal
from threading import local as nlocal

class GLocalSub(glocal):
    pass

class NativeSub(nlocal):
    pass


benchmarks = []


def _populate(l):
    for i in range(10):
        setattr(l, 'attr' + str(i), i)


def bench_getattr(loops, local):
    t0 = perf.perf_counter()

    for _ in range(loops):
        # pylint:disable=pointless-statement
        local.attr0
        local.attr1
        local.attr2
        local.attr3
        local.attr4
        local.attr5
        local.attr6
        local.attr7
        local.attr8
        local.attr9

    return perf.perf_counter() - t0

def bench_setattr(loops, local):
    t0 = perf.perf_counter()

    for _ in range(loops):
        local.attr0 = 0
        local.attr1 = 1
        local.attr2 = 2
        local.attr3 = 3
        local.attr4 = 4
        local.attr5 = 5
        local.attr6 = 6
        local.attr7 = 7
        local.attr8 = 8
        local.attr9 = 9

    return perf.perf_counter() - t0

def main():
    runner = perf.Runner()

    for name, obj in (('gevent', glocal()),
                      ('gevent sub', GLocalSub()),
                      ('native', nlocal()),
                      ('native sub', NativeSub())):
        _populate(obj)

        benchmarks.append(
            runner.bench_time_func('getattr ' + name,
                                   bench_getattr,
                                   obj,
                                   inner_loops=10))

        benchmarks.append(
            runner.bench_time_func('setattr ' + name,
                                   bench_setattr,
                                   obj,
                                   inner_loops=10))


if __name__ == '__main__':
    main()
