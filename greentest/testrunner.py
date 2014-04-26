#!/usr/bin/env python
from __future__ import print_function
import six
import sys
import os
import glob
import traceback
import time
from datetime import timedelta

from multiprocessing.pool import ThreadPool
import util
from util import log


TIMEOUT = 180
NWORKERS = int(os.environ.get('NWORKERS') or 8)


def run_many(tests, expected=None, failfast=False):
    global NWORKERS
    start = time.time()
    total = 0
    failed = {}

    NWORKERS = min(len(tests), NWORKERS) or 1
    pool = ThreadPool(NWORKERS)
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

    results = []

    def reap():
        for r in results[:]:
            if not r.ready():
                continue
            if r.successful():
                results.remove(r)
            else:
                r.get()
                sys.exit('Internal error in testrunner.py: %r' % (r, ))
        return len(results)

    def reap_all():
        while reap() > 0:
            time.sleep(0.1)

    def spawn(args, kwargs):
        while True:
            if reap() < NWORKERS:
                r = pool.apply_async(run_one, (cmd, ), options or {})
                results.append(r)
                return
            else:
                time.sleep(0.1)

    try:
        try:
            for cmd, options in tests:
                total += 1
                spawn((cmd, ), options or {})
            pool.close()
            pool.join()
        except KeyboardInterrupt:
            try:
                log('Waiting for currently running to finish...')
                reap_all()
            except KeyboardInterrupt:
                pool.terminate()
                report(total, failed, exit=False, took=time.time() - start, expected=expected)
                log('(partial results)\n')
                raise
    except:
        traceback.print_exc()
        pool.terminate()
        raise

    reap_all()

    toretry = [key for (key, (cmd, kwargs, can_retry)) in failed.items() if can_retry]
    failed_then_succeeded = []

    if NWORKERS > 1 and toretry:
        log('\nWill retry %s failed tests sequentially:\n- %s\n', len(toretry), '\n- '.join(toretry))
        for name, (cmd, kwargs, _ignore) in list(failed.items()):
            if not util.run(cmd, buffer_output=False, **kwargs):
                failed.pop(name)
                failed_then_succeeded.append(name)

    if failed_then_succeeded:
        log('\n%s tests failed during concurrent run but succeeded when ran sequentially:', len(failed_then_succeeded))
        log('- ' + '\n- '.join(failed_then_succeeded))

    util.report(total, failed, took=time.time() - start, expected=expected)


def discover(tests=None, ignore=None):
    if isinstance(ignore, six.string_types):
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


def matches(expected, command):
    for line in expected:
        if command.endswith(' ' + line):
            return True
    return False


def format_seconds(seconds):
    if seconds < 20:
        return '%.1fs' % seconds
    seconds = str(timedelta(seconds=round(seconds)))
    if seconds.startswith('0:'):
        seconds = seconds[2:]
    return seconds


def report(total, failed, exit=True, took=None, expected=None):
    runtimelog = util.runtimelog
    if runtimelog:
        log('\nLongest-running tests:')
        runtimelog.sort()
        length = len('%.1f' % -runtimelog[0][0])
        frmt = '%' + str(length) + '.1f seconds: %s'
        for delta, name in runtimelog[:5]:
            log(frmt, -delta, name)
    if took:
        took = ' in %s' % format_seconds(took)
    else:
        took = ''

    failed_expected = []
    failed_unexpected = []

    if failed:
        log('\n%s/%s tests failed%s', len(failed), total, took)
        expected = set(expected or [])
        for name in failed:
            if matches(expected, name):
                failed_expected.append(name)
            else:
                failed_unexpected.append(name)

        if failed_expected:
            log('\n%s/%s expected failures', len(failed_expected), total)
            for name in failed_expected:
                log(' - %s', name)

        if failed_unexpected:
            log('\n%s/%s unexpected failures', len(failed_unexpected), total)
            for name in failed_unexpected:
                log(' - %s', name)
    else:
        log('\n%s tests passed%s', total, took)
    if exit:
        if failed_unexpected:
            sys.exit(min(100, len(failed_unexpected)))
        if total <= 0:
            sys.exit('No tests found.')


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--ignore')
    parser.add_option('--discover', action='store_true')
    parser.add_option('--full', action='store_true')
    parser.add_option('--config')
    parser.add_option('--failfast', action='store_true')
    options, args = parser.parse_args()
    FAILING_TESTS = []
    if options.config:
        config = {}
        six.exec_(open(options.config).read(), config)
        FAILING_TESTS = config['FAILING_TESTS']
    tests = discover(args, options.ignore)
    if options.discover:
        for cmd, options in tests:
            print(util.getname(cmd, env=options.get('env'), setenv=options.get('setenv')))
        print('%s tests found.' % len(tests))
    else:
        run_many(tests, expected=FAILING_TESTS, failfast=options.failfast)


if __name__ == '__main__':
    main()
