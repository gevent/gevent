#!/usr/bin/env python
import gevent
gevent.get_hub('select')
from gevent import monkey; monkey.patch_all()
import sys
import os
import glob
import time

from gevent.pool import Pool
import util


TIMEOUT = 120
NWORKERS = int(os.environ.get('NWORKERS') or 8)
pool = None


def info():
    lastmsg = None
    while True:
        gevent.sleep(10, ref=False)
        if pool:
            msg = '# Currently running: %s: %s' % (len(pool), ', '.join(x.name for x in pool))
            if msg != lastmsg:
                lastmsg = msg
                util.log(msg)


def spawn(*args, **kwargs):
    g = pool.spawn(*args, **kwargs)
    g.link_exception(lambda *args: sys.exit('Internal error'))
    return g


def run_many(tests):
    global NWORKERS, pool
    start = time.time()
    total = 0
    failed = {}

    tests = list(tests)
    NWORKERS = min(len(tests), NWORKERS)
    pool = Pool(NWORKERS)
    util.BUFFER_OUTPUT = NWORKERS > 1

    def run_one(name, cmd, **kwargs):
        result = util.run(cmd, **kwargs)
        if result:
            # the tests containing AssertionError might have failed because
            # we spawned more workers than CPUs
            # we therefore will retry them sequentially
            failed[name] = [cmd, kwargs, 'AssertionError' in (result.output or '')]

    if NWORKERS > 1:
        gevent.spawn(info)

    try:
        try:
            for name, cmd, options in tests:
                total += 1
                spawn(run_one, name, cmd, **options).name = ' '.join(cmd)
            gevent.run()
        except KeyboardInterrupt:
            try:
                if pool:
                    util.log('Waiting for currently running to finish...')
                    pool.join()
            except KeyboardInterrupt:
                util.report(total, failed, exit=False, took=time.time() - start)
                util.log('(partial results)\n')
                raise
    except:
        pool.kill()  # this needed to kill the processes
        raise

    toretry = [key for (key, (cmd, kwargs, can_retry)) in failed.items() if can_retry]
    failed_then_succeeded = []

    if NWORKERS > 1 and toretry:
        util.log('\nWill re-try %s failed tests without concurrency:\n- %s\n', len(toretry), '\n- '.join(toretry))
        for name, (cmd, kwargs, _ignore) in failed.items():
            if not util.run(cmd, buffer_output=False, **kwargs):
                failed.pop(name)
                failed_then_succeeded.append(name)

    util.report(total, failed, took=time.time() - start)

    if failed_then_succeeded:
        util.log('\n%s tests failed during concurrent run but succeeded when ran sequentially:', len(failed_then_succeeded))
        util.log('- ' + '\n- '.join(failed_then_succeeded))
    assert not pool, pool

    os.system('rm -f */@test*_tmp')


def discover(tests):
    if not tests:
        tests = set(glob.glob('test_*.py')) - set(['test_support.py'])
        tests = sorted(tests)

    to_process = []
    default_options = {'timeout': TIMEOUT}

    for filename in tests:
        if 'TESTRUNNER' in open(filename).read():
            module = __import__(filename.rsplit('.', 1)[0])
            for name, cmd, options in module.TESTRUNNER():
                to_process.append((filename + ' ' + name, cmd, options))
        else:
            to_process.append((filename, [sys.executable, '-u', filename], default_options))

    return to_process


def main():
    run_many(discover(sys.argv[1:]))


if __name__ == '__main__':
    main()
