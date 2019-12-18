"""
Benchmarking spawn() performance.
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from pyperf import perf_counter
from pyperf import Runner

try:
    xrange
except NameError:
    xrange = range


N = 10000
counter = 0


def incr(**_kwargs):
    global counter
    counter += 1


def noop(_p):
    pass

class Options(object):

    # TODO: Add back an argument for that
    eventlet_hub = None

    loops = None

    def __init__(self, sleep, join, **kwargs):
        self.kwargs = kwargs
        self.sleep = sleep
        self.join = join

class Times(object):

    def __init__(self,
                 spawn_duration,
                 sleep_duration=-1,
                 join_duration=-1):
        self.spawn_duration = spawn_duration
        self.sleep_duration = sleep_duration
        self.join_duration = join_duration


def _test(spawn, sleep, options):
    global counter
    counter = 0
    before_spawn = perf_counter()
    for _ in xrange(N):
        spawn(incr, **options.kwargs)
    spawn_duration = perf_counter() - before_spawn


    if options.sleep:
        assert counter == 0, counter
        before_sleep = perf_counter()
        sleep(0)
        sleep_duration = perf_counter() - before_sleep
        assert counter == N, (counter, N)
    else:
        sleep_duration = -1


    if options.join:
        before_join = perf_counter()
        options.join()
        join_duration = perf_counter() - before_join
    else:
        join_duration = -1

    return Times(spawn_duration,
                 sleep_duration,
                 join_duration)

def test(spawn, sleep, options):
    all_times = [
        _test(spawn, sleep, options)
        for _ in xrange(options.loops)
    ]

    spawn_duration = sum(x.spawn_duration for x in all_times)
    sleep_duration = sum(x.sleep_duration for x in all_times)
    join_duration = sum(x.sleep_duration for x in all_times
                        if x != -1)

    return Times(spawn_duration, sleep_duration, join_duration)

def bench_none(options):
    from time import sleep

    options.sleep = False

    def spawn(f, **kwargs):
        return f(**kwargs)

    return test(spawn,
                sleep,
                options)


def bench_gevent(options):
    from gevent import spawn, sleep
    return test(spawn, sleep, options)


def bench_geventraw(options):
    from gevent import sleep, spawn_raw
    return test(spawn_raw, sleep, options)


def bench_geventpool(options):
    from gevent import sleep
    from gevent.pool import Pool
    p = Pool()
    if options.join:
        options.join = p.join
    times = test(p.spawn, sleep, options)
    return times


try:
    __import__('eventlet')
except ImportError:
    pass
else:
    def bench_eventlet(options):
        from eventlet import spawn, sleep
        if options.eventlet_hub is not None:
            from eventlet.hubs import use_hub
            use_hub(options.eventlet_hub)
        return test(spawn, sleep, options)


def all():
    result = [x for x in globals() if x.startswith('bench_') and x != 'bench_all']
    result.sort()
    result = [x.replace('bench_', '') for x in result]
    return result



def main(argv=None):
    import os
    import sys
    if argv is None:
        argv = sys.argv[1:]

    env_options = [
        '--inherit-environ',
        ','.join([k for k in os.environ
                  if k.startswith(('GEVENT',
                                   'PYTHON',
                                   'ZS', # experimental zodbshootout config
                                   'RS', # relstorage config
                                   'COVERAGE'))])]
    # This is a default, so put it early
    argv[0:0] = env_options

    def worker_cmd(cmd, args):
        cmd.extend(args.benchmark)

    runner = Runner(add_cmdline_args=worker_cmd)
    runner.argparser.add_argument('benchmark',
                                  nargs='*',
                                  default='all',
                                  choices=all() + ['all'])

    def spawn_time(loops, func, options):
        options.loops = loops
        times = func(options)
        return times.spawn_duration

    def sleep_time(loops, func, options):
        options.loops = loops
        times = func(options)
        return times.sleep_duration

    def join_time(loops, func, options):
        options.loops = loops
        times = func(options)
        return times.join_duration

    args = runner.parse_args(argv)

    if 'all' in args.benchmark or args.benchmark == 'all':
        args.benchmark = ['all']
        names = all()
    else:
        names = args.benchmark

    names = sorted(set(names))

    for name in names:
        runner.bench_time_func(name + ' spawn',
                               spawn_time,
                               globals()['bench_' + name],
                               Options(sleep=False, join=False),
                               inner_loops=N)

        if name != 'none':
            runner.bench_time_func(name + ' sleep',
                                   sleep_time,
                                   globals()['bench_' + name],
                                   Options(sleep=True, join=False),
                                   inner_loops=N)

    if 'geventpool' in names:
        runner.bench_time_func('geventpool join',
                               join_time,
                               bench_geventpool,
                               Options(sleep=True, join=True),
                               inner_loops=N)

    for name in names:
        runner.bench_time_func(name + ' spawn kwarg',
                               spawn_time,
                               globals()['bench_' + name],
                               Options(sleep=False, join=False, foo=1, bar='hello'),
                               inner_loops=N)


if __name__ == '__main__':
    main()
