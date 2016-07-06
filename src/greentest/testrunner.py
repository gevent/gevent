#!/usr/bin/env python
from __future__ import print_function
import _six as six
import sys
import os
import glob
import traceback
import time
from datetime import timedelta

from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count
import util
from util import log


TIMEOUT = 180
NWORKERS = int(os.environ.get('NWORKERS') or max(cpu_count() - 1, 4))
if NWORKERS > 10:
    NWORKERS = 10


RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR

if RUNNING_ON_CI:
    # Too many and we get spurious timeouts
    NWORKERS = 6


# tests that don't do well when run on busy box
RUN_ALONE = [
    'test__threadpool.py',
    'test__examples.py'
]

# tests that can't be run when coverage is enabled
IGNORE_COVERAGE = [
    # Hangs forever
    'test__threading_vs_settrace.py',
    # XXX ?
    'test__issue302monkey.py',
    "test_subprocess.py",
]


def run_many(tests, expected=(), failfast=False):
    # pylint:disable=too-many-locals
    global NWORKERS
    start = time.time()
    total = 0
    failed = {}
    passed = {}

    NWORKERS = min(len(tests), NWORKERS) or 1
    print('thread pool size: %s' % NWORKERS)
    pool = ThreadPool(NWORKERS)
    util.BUFFER_OUTPUT = NWORKERS > 1

    def run_one(cmd, **kwargs):
        result = util.run(cmd, **kwargs)
        if result:
            if failfast:
                sys.exit(1)
            failed[result.name] = [cmd, kwargs]
        else:
            passed[result.name] = True

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

    def spawn(args, kwargs): # pylint:disable=unused-argument
        while True:
            if reap() < NWORKERS:
                r = pool.apply_async(run_one, (cmd, ), options or {})
                results.append(r)
                return
            else:
                time.sleep(0.1)

    run_alone = []

    try:
        try:
            for cmd, options in tests:
                total += 1
                options = options or {}
                if matches(RUN_ALONE, cmd):
                    run_alone.append((cmd, options))
                else:
                    spawn((cmd, ), options)
            pool.close()
            pool.join()

            for cmd, options in run_alone:
                run_one(cmd, **options)

        except KeyboardInterrupt:
            try:
                log('Waiting for currently running to finish...')
                reap_all()
            except KeyboardInterrupt:
                pool.terminate()
                report(total, failed, passed, exit=False, took=time.time() - start, expected=expected)
                log('(partial results)\n')
                raise
    except:
        traceback.print_exc()
        pool.terminate()
        raise

    reap_all()
    report(total, failed, passed, took=time.time() - start, expected=expected)


def discover(tests=None, ignore=(), coverage=False):
    if isinstance(ignore, six.string_types):
        ignore = set(load_list_from_file(ignore))

    ignore = set(ignore or ())
    if coverage:
        ignore.update(IGNORE_COVERAGE)

    if not tests:
        tests = set(glob.glob('test_*.py')) - set(['test_support.py'])
    else:
        tests = set(tests)

    if ignore:
        # Always ignore the designated list, even if tests were specified
        # on the command line. This fixes a nasty interaction with test__threading_vs_settrace.py
        # being run under coverage when 'grep -l subprocess test*py' is used to list the tests
        # to run.
        tests -= ignore
    tests = sorted(tests)

    to_process = []
    default_options = {'timeout': TIMEOUT}

    for filename in tests:
        with open(filename, 'rb') as f:
            # Some of the test files (e.g., test__socket_dns) are
            # UTF8 encoded. Depending on the environment, Python 3 may
            # try to decode those as ASCII, which fails with UnicodeDecodeError.
            # Thus, be sure to open and compare in binary mode.
            contents = f.read()
        if b'TESTRUNNER' in contents: # test__monkey_patching.py
            module = __import__(filename.rsplit('.', 1)[0])
            for cmd, options in module.TESTRUNNER():
                if remove_options(cmd)[-1] in ignore:
                    continue
                to_process.append((cmd, options))
        else:
            cmd = [sys.executable, '-u', filename]
            to_process.append((cmd, default_options.copy()))

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


def matches(expected, command, include_flaky=True):
    if isinstance(command, list):
        command = ' '.join(command)
    for line in expected:
        if not include_flaky and line.startswith('FLAKY '):
            continue
        if command.endswith(' ' + line.replace('FLAKY ', '')):
            return True
    return False


def format_seconds(seconds):
    if seconds < 20:
        return '%.1fs' % seconds
    seconds = str(timedelta(seconds=round(seconds)))
    if seconds.startswith('0:'):
        seconds = seconds[2:]
    return seconds


def report(total, failed, passed, exit=True, took=None, expected=None):
    # pylint:disable=redefined-builtin,too-many-branches
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
    passed_unexpected = []

    for name in passed:
        if matches(expected, name, include_flaky=False):
            passed_unexpected.append(name)

    if passed_unexpected:
        log('\n%s/%s unexpected passes', len(passed_unexpected), total)
        print_list(passed_unexpected)

    if failed:
        log('\n%s/%s tests failed%s', len(failed), total, took)
        expected = set(expected or [])
        for name in failed:
            if matches(expected, name, include_flaky=True):
                failed_expected.append(name)
            else:
                failed_unexpected.append(name)

        if failed_expected:
            log('\n%s/%s expected failures', len(failed_expected), total)
            print_list(failed_expected)

        if failed_unexpected:
            log('\n%s/%s unexpected failures', len(failed_unexpected), total)
            print_list(failed_unexpected)
    else:
        log('\n%s tests passed%s', total, took)

    if exit:
        if failed_unexpected:
            sys.exit(min(100, len(failed_unexpected)))
        if passed_unexpected:
            sys.exit(101)
        if total <= 0:
            sys.exit('No tests found.')


def print_list(lst):
    for name in lst:
        log(' - %s', name)


def main():
    # FIXME: transition to argparse
    import optparse # pylint:disable=deprecated-module
    parser = optparse.OptionParser()
    parser.add_option('--ignore')
    parser.add_option('--discover', action='store_true')
    parser.add_option('--full', action='store_true')
    parser.add_option('--config')
    parser.add_option('--failfast', action='store_true')
    parser.add_option("--coverage", action="store_true")
    options, args = parser.parse_args()
    FAILING_TESTS = []
    coverage = False
    if options.coverage or os.environ.get("GEVENTTEST_COVERAGE"):
        coverage = True
        # NOTE: This must be run from the greentest directory
        os.environ['COVERAGE_PROCESS_START'] = os.path.abspath(".coveragerc")
        os.environ['PYTHONPATH'] = os.path.abspath("coveragesite") + os.pathsep + os.environ.get("PYTHONPATH", "")
        # We change directory often, use an absolute path to keep all the
        # coverage files (which will have distinct suffixes because of parallel=true in .coveragerc
        # in this directory; makes them easier to combine and use with coverage report)
        os.environ['COVERAGE_FILE'] = os.path.abspath(".") + os.sep + ".coverage"
        print("Enabling coverage to", os.environ['COVERAGE_FILE'])
    if options.config:
        config = {}
        with open(options.config) as f:
            config_data = f.read()
        six.exec_(config_data, config)
        FAILING_TESTS = config['FAILING_TESTS']
    tests = discover(args, options.ignore, coverage)
    if options.discover:
        for cmd, options in tests:
            print(util.getname(cmd, env=options.get('env'), setenv=options.get('setenv')))
        print('%s tests found.' % len(tests))
    else:
        run_many(tests, expected=FAILING_TESTS, failfast=options.failfast)


if __name__ == '__main__':
    main()
