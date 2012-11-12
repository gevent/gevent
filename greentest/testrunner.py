#!/usr/bin/env python
import gevent
gevent.get_hub('select')  # this is just to make sure we don't pass any fds to children
from gevent import monkey; monkey.patch_all()
import sys
import os
import glob
import traceback
from time import time

from gevent.pool import Pool
import util


TIMEOUT = 180
NWORKERS = int(os.environ.get('NWORKERS') or 8)
pool = None


def spawn(*args, **kwargs):
    g = pool.spawn(*args, **kwargs)
    g.link_exception(lambda *args: sys.exit('Internal error in testrunner.py: %s %s' % (g, g.exception)))
    return g


def run_many(tests, expected=None, failfast=False):
    global NWORKERS, pool
    start = time()
    total = 0
    failed = {}

    NWORKERS = min(len(tests), NWORKERS)
    pool = Pool(NWORKERS)
    util.BUFFER_OUTPUT = NWORKERS > 1

    def run_one(cmd, **kwargs):
        result = util.run(cmd, **kwargs)
        if result:
            if failfast:
                sys.exit(1)
            # the tests containing AssertionError might have failed because
            # we spawned more workers than CPUs
            # we therefore will retry them sequentially
            failed[result.name] = [cmd, kwargs, 'AssertionError' in (result.output or '')]

    try:
        try:
            for cmd, options in tests:
                total += 1
                spawn(run_one, cmd, **(options or {}))
            gevent.wait()
        except KeyboardInterrupt:
            try:
                if pool:
                    util.log('Waiting for currently running to finish...')
                    pool.join()
            except KeyboardInterrupt:
                util.report(total, failed, exit=False, took=time() - start, expected=expected)
                util.log('(partial results)\n')
                raise
    except:
        traceback.print_exc()
        pool.kill()  # this needed to kill the processes
        raise

    toretry = [key for (key, (cmd, kwargs, can_retry)) in failed.items() if can_retry]
    failed_then_succeeded = []

    if NWORKERS > 1 and toretry:
        util.log('\nWill retry %s failed tests sequentially:\n- %s\n', len(toretry), '\n- '.join(toretry))
        for name, (cmd, kwargs, _ignore) in failed.items():
            if not util.run(cmd, buffer_output=False, **kwargs):
                failed.pop(name)
                failed_then_succeeded.append(name)

    if failed_then_succeeded:
        util.log('\n%s tests failed during concurrent run but succeeded when ran sequentially:', len(failed_then_succeeded))
        util.log('- ' + '\n- '.join(failed_then_succeeded))

    util.log('gevent version %s from %s', gevent.__version__, gevent.__file__)
    util.report(total, failed, took=time() - start, expected=expected)
    assert not pool, pool


def discover(tests=None, ignore=None):
    if isinstance(ignore, basestring):
        ignore = load_list_from_file(ignore)

    ignore = set(ignore or [])

    if not tests:
        tests = set(glob.glob('test_*.py')) - set(['test_support.py'])
        if ignore:
            tests -= ignore
        tests = sorted(tests)

    to_process = []
    default_options = {'timeout': TIMEOUT}

    for filename in tests:
        if 'TESTRUNNER' in open(filename).read():
            module = __import__(filename.rsplit('.', 1)[0])
            for cmd, options in module.TESTRUNNER():
                if remove_options(cmd)[-1] in ignore:
                    continue
                to_process.append((cmd, options))
        else:
            to_process.append(([sys.executable, '-u', filename], default_options.copy()))

    return to_process


def remove_options(lst):
    return [x for x in lst if x and not x.startswith('-')]


def load_list_from_file(filename):
    result = []
    if filename:
        for x in open(filename):
            x = x.split('#', 1)[0].strip()
            if x:
                result.append(x)
    return result


def full(args=None):
    tests = []

    for setenv, ignore in [('GEVENT_RESOLVER=thread', None),
                           ('GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8', 'tests_that_dont_use_resolver.txt')]:
        setenv = dict(x.split('=') for x in setenv.split())
        for cmd, options in discover(args, ignore=ignore):
            my_setenv = options.get('setenv', {})
            my_setenv.update(setenv)
            options['setenv'] = my_setenv
            tests.append((cmd, options))

    if sys.version_info[:2] == (2, 7) and os.environ.get('EXTRA'):
        tests.append(([sys.executable, '-u', 'xtest_pep8.py'], None))

    return tests


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--ignore')
    parser.add_option('--discover', action='store_true')
    parser.add_option('--full', action='store_true')
    parser.add_option('--expected')
    parser.add_option('--failfast', action='store_true')
    options, args = parser.parse_args()
    options.expected = load_list_from_file(options.expected)
    if options.full:
        assert options.ignore is None, '--ignore and --full are not compatible'
        tests = full(args)
    else:
        tests = discover(args, options.ignore)
    if options.discover:
        for cmd, options in tests:
            print util.getname(cmd, env=options.get('env'), setenv=options.get('setenv'))
        print '%s tests found.' % len(tests)
    else:
        run_many(tests, expected=options.expected, failfast=options.failfast)


if __name__ == '__main__':
    main()
