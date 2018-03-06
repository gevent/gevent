#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import sys
import os
import glob
import traceback
import time
from datetime import timedelta

from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count
from greentest import util
from greentest.util import log
from greentest.sysinfo import RUNNING_ON_CI
from greentest.sysinfo import PYPY
from greentest.sysinfo import PY3
from greentest.sysinfo import PY2
from greentest.sysinfo import RESOLVER_ARES
from greentest.sysinfo import LIBUV
from greentest import six

# Import this while we're probably single-threaded/single-processed
# to try to avoid issues with PyPy 5.10.
# See https://bitbucket.org/pypy/pypy/issues/2769/systemerror-unexpected-internal-exception
try:
    __import__('_testcapi')
except (ImportError, OSError, IOError):
    # This can raise a wide variety of errors
    pass

TIMEOUT = 100
NWORKERS = int(os.environ.get('NWORKERS') or max(cpu_count() - 1, 4))
if NWORKERS > 10:
    NWORKERS = 10

DEFAULT_RUN_OPTIONS = {
    'timeout': TIMEOUT
}

# A mapping from test file basename to a dictionary of
# options that will be applied on top of the DEFAULT_RUN_OPTIONS.
TEST_FILE_OPTIONS = {

}

if RUNNING_ON_CI:
    # Too many and we get spurious timeouts
    NWORKERS = 4


# tests that don't do well when run on busy box
RUN_ALONE = [
    'test__threadpool.py',
    'test__examples.py',
]

if RUNNING_ON_CI:
    RUN_ALONE += [
        # Partial workaround for the _testcapi issue on PyPy,
        # but also because signal delivery can sometimes be slow, and this
        # spawn processes of its own
        'test_signal.py',
    ]
    if PYPY:
        # This often takes much longer on PyPy on CI.
        TEST_FILE_OPTIONS['test__threadpool.py'] = {'timeout': 180}
        if PY3:
            RUN_ALONE += [
                # Sometimes shows unexpected timeouts
                'test_socket.py',
            ]
        if LIBUV:
            RUN_ALONE += [
                # https://bitbucket.org/pypy/pypy/issues/2769/systemerror-unexpected-internal-exception
                'test__pywsgi.py',
            ]

# tests that can't be run when coverage is enabled
IGNORE_COVERAGE = [
    # Hangs forever
    'test__threading_vs_settrace.py',
    # times out
    'test_socket.py',
    # Doesn't get the exceptions it expects
    'test_selectors.py',
    # XXX ?
    'test__issue302monkey.py',
    "test_subprocess.py",
]

if PYPY:
    IGNORE_COVERAGE += [
        # Tends to timeout
        'test__refcount.py',
        'test__greenletset.py'
    ]


def run_many(tests, configured_failing_tests=(), failfast=False, quiet=False):
    # pylint:disable=too-many-locals
    global NWORKERS
    start = time.time()
    total = 0
    failed = {}
    passed = {}

    NWORKERS = min(len(tests), NWORKERS) or 1

    pool = ThreadPool(NWORKERS)
    util.BUFFER_OUTPUT = NWORKERS > 1

    def run_one(cmd, **kwargs):
        kwargs['quiet'] = quiet
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

    def spawn(cmd, options):
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
            log("Running tests in parallel with concurrency %s" % (NWORKERS,))
            for cmd, options in tests:
                total += 1
                options = options or {}
                if matches(RUN_ALONE, cmd):
                    run_alone.append((cmd, options))
                else:
                    spawn(cmd, options)
            pool.close()
            pool.join()

            log("Running tests marked standalone")
            for cmd, options in run_alone:
                run_one(cmd, **options)

        except KeyboardInterrupt:
            try:
                log('Waiting for currently running to finish...')
                reap_all()
            except KeyboardInterrupt:
                pool.terminate()
                report(total, failed, passed, exit=False, took=time.time() - start,
                       configured_failing_tests=configured_failing_tests)
                log('(partial results)\n')
                raise
    except:
        traceback.print_exc()
        pool.terminate()
        raise

    reap_all()
    report(total, failed, passed, took=time.time() - start,
           configured_failing_tests=configured_failing_tests)


def discover(tests=None, ignore_files=None,
             ignored=(), coverage=False):
    ignore = set(ignored or ())
    if ignore_files:
        ignore_files = ignore_files.split(',')
        for f in ignore_files:
            ignore.update(set(load_list_from_file(f)))

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
            cmd = [sys.executable, '-u']
            if PYPY and PY2:
                # Doesn't seem to be an env var for this
                cmd.extend(('-X', 'track-resources'))
            cmd.append(filename)
            options = DEFAULT_RUN_OPTIONS.copy()
            options.update(TEST_FILE_OPTIONS.get(filename, {}))
            to_process.append((cmd, options))

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


def matches(possibilities, command, include_flaky=True):
    if isinstance(command, list):
        command = ' '.join(command)
    for line in possibilities:
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


def report(total, failed, passed, exit=True, took=None,
           configured_failing_tests=()):
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
        if matches(configured_failing_tests, name, include_flaky=False):
            passed_unexpected.append(name)

    if passed_unexpected:
        log('\n%s/%s unexpected passes', len(passed_unexpected), total)
        print_list(passed_unexpected)

    if failed:
        log('\n%s/%s tests failed%s', len(failed), total, took)

        for name in failed:
            if matches(configured_failing_tests, name, include_flaky=True):
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

def _setup_environ():
    if 'PYTHONWARNINGS' not in os.environ and not sys.warnoptions:
        # Enable default warnings such as ResourceWarning.
        # On Python 3[.6], the system site.py module has
        # "open(fullname, 'rU')" which produces the warning that
        # 'U' is deprecated, so ignore warnings from site.py

        # importlib/_bootstrap.py likes to spit out "ImportWarning:
        # can't resolve package from __spec__ or __package__, falling
        # back on __name__ and __path__". I have no idea what that means, but it seems harmless
        # and is annoying.
        os.environ['PYTHONWARNINGS'] = 'default,ignore:::site:,ignore:::importlib._bootstrap:,ignore:::importlib._bootstrap_external:'

    if 'PYTHONFAULTHANDLER' not in os.environ:
        os.environ['PYTHONFAULTHANDLER'] = 'true'

    if 'GEVENT_DEBUG' not in os.environ:
        os.environ['GEVENT_DEBUG'] = 'debug'

    if 'PYTHONTRACEMALLOC' not in os.environ:
        os.environ['PYTHONTRACEMALLOC'] = '10'

    if 'PYTHONDEVMODE' not in os.environ:
        # Python 3.7
        os.environ['PYTHONDEVMODE'] = '1'

    if 'PYTHONMALLOC' not in os.environ:
        # Python 3.6
        os.environ['PYTHONMALLOC'] = 'debug'

    if (sys.version_info == (3, 7, 0, 'beta', 2)
            and (os.environ.get("PYTHONDEVMODE") or os.environ.get('PYTHONMALLOC'))):
        # See https://twitter.com/ossmkitty/status/970693025130311680
        # https://bugs.python.org/issue33005
        os.environ.pop('PYTHONDEVMODE', None)
        os.environ.pop('PYTHONMALLOC', None)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ignore')
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--config', default='known_failures.py')
    parser.add_argument('--failfast', action='store_true')
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--quiet", action="store_true", default=True)
    parser.add_argument("--verbose", action="store_false", dest='quiet')
    parser.add_argument('tests', nargs='*')
    options = parser.parse_args()
    FAILING_TESTS = []
    IGNORED_TESTS = []
    coverage = False
    if options.coverage or os.environ.get("GEVENTTEST_COVERAGE"):
        coverage = True
        # NOTE: This must be run from the greentest directory
        os.environ['COVERAGE_PROCESS_START'] = os.path.abspath(".coveragerc")
        if PYPY:
            os.environ['COVERAGE_PROCESS_START'] = os.path.abspath(".coveragerc-pypy")
        os.environ['PYTHONPATH'] = os.path.abspath("coveragesite") + os.pathsep + os.environ.get("PYTHONPATH", "")
        # We change directory often, use an absolute path to keep all the
        # coverage files (which will have distinct suffixes because of parallel=true in .coveragerc
        # in this directory; makes them easier to combine and use with coverage report)
        os.environ['COVERAGE_FILE'] = os.path.abspath(".") + os.sep + ".coverage"
        print("Enabling coverage to", os.environ['COVERAGE_FILE'])

    _setup_environ()

    if options.config:
        config = {}
        with open(options.config) as f:
            config_data = f.read()
        six.exec_(config_data, config)
        FAILING_TESTS = config['FAILING_TESTS']
        IGNORED_TESTS = config['IGNORED_TESTS']



    tests = discover(options.tests,
                     ignore_files=options.ignore,
                     ignored=IGNORED_TESTS,
                     coverage=coverage)
    if options.discover:
        for cmd, options in tests:
            print(util.getname(cmd, env=options.get('env'), setenv=options.get('setenv')))
        print('%s tests found.' % len(tests))
    else:
        if PYPY and RESOLVER_ARES:
            # XXX: Add a way to force these.
            print("Not running tests on pypy with c-ares; not a supported configuration")
            return
        run_many(tests, configured_failing_tests=FAILING_TESTS, failfast=options.failfast, quiet=options.quiet)


if __name__ == '__main__':
    main()
