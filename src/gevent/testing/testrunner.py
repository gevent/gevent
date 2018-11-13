#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import sys
import os
import glob
import traceback
import time
import importlib
from datetime import timedelta

from multiprocessing.pool import ThreadPool
from multiprocessing import cpu_count
from . import util
from .util import log
from .sysinfo import RUNNING_ON_CI
from .sysinfo import PYPY
from .sysinfo import PY2
from .sysinfo import RESOLVER_ARES
from .sysinfo import RUN_LEAKCHECKS
from . import six

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

if RUN_LEAKCHECKS:
    # Capturing the stats takes time, and we run each
    # test at least twice
    TIMEOUT = 200

DEFAULT_RUN_OPTIONS = {
    'timeout': TIMEOUT
}


if RUNNING_ON_CI:
    # Too many and we get spurious timeouts
    NWORKERS = 4




def _package_relative_filename(filename, package):
    if not os.path.isfile(filename) and package:
        # Ok, try to locate it as a module in the package
        package_dir = _dir_from_package_name(package)
        return os.path.join(package_dir, filename)
    return filename

def _dir_from_package_name(package):
    package_mod = importlib.import_module(package)
    package_dir = os.path.dirname(package_mod.__file__)
    return package_dir


def run_many(tests,
             configured_failing_tests=(),
             failfast=False,
             quiet=False,
             configured_run_alone_tests=()):
    # pylint:disable=too-many-locals,too-many-statements
    global NWORKERS
    start = time.time()
    total = 0
    failed = {}
    passed = {}
    total_cases = [0]
    total_skipped = [0]

    NWORKERS = min(len(tests), NWORKERS) or 1

    pool = ThreadPool(NWORKERS)
    util.BUFFER_OUTPUT = NWORKERS > 1 or quiet

    def run_one(cmd, **kwargs):
        kwargs['quiet'] = quiet
        result = util.run(cmd, **kwargs)
        if result:
            if failfast:
                sys.exit(1)
            failed[result.name] = [cmd, kwargs]
        else:
            passed[result.name] = True
        total_cases[0] += result.run_count
        total_skipped[0] += result.skipped_count

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

            time.sleep(0.05)

    run_alone = []

    try:
        try:
            log("Running tests in parallel with concurrency %s" % (NWORKERS,),)
            for cmd, options in tests:
                total += 1
                options = options or {}
                if matches(configured_run_alone_tests, cmd):
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
                       configured_failing_tests=configured_failing_tests,
                       total_cases=total_cases[0], total_skipped=total_skipped[0])
                log('(partial results)\n')
                raise
    except:
        traceback.print_exc()
        pool.terminate()
        raise

    reap_all()
    report(total, failed, passed, took=time.time() - start,
           configured_failing_tests=configured_failing_tests,
           total_cases=total_cases[0], total_skipped=total_skipped[0])

def discover(
        tests=None, ignore_files=None,
        ignored=(), coverage=False,
        package=None,
        configured_ignore_coverage=(),
        configured_test_options=None,
):
    # pylint:disable=too-many-locals,too-many-branches
    configured_test_options = configured_test_options or {}
    olddir = os.getcwd()
    ignore = set(ignored or ())

    if ignore_files:
        ignore_files = ignore_files.split(',')
        for f in ignore_files:
            ignore.update(set(load_list_from_file(f, package)))

    if coverage:
        ignore.update(configured_ignore_coverage)

    if package:
        package_dir = _dir_from_package_name(package)
        # We need to glob relative names, our config is based on filenames still
        os.chdir(package_dir)

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
    to_import = []

    for filename in tests:
        module_name = os.path.splitext(filename)[0]
        qualified_name = package + '.' + module_name if package else module_name
        with open(os.path.abspath(filename), 'rb') as f:
            # Some of the test files (e.g., test__socket_dns) are
            # UTF8 encoded. Depending on the environment, Python 3 may
            # try to decode those as ASCII, which fails with UnicodeDecodeError.
            # Thus, be sure to open and compare in binary mode.
            # Open the absolute path to make errors more clear,
            # but we can't store the absolute path, our configuration is based on
            # relative file names.
            contents = f.read()
        if b'TESTRUNNER' in contents: # test__monkey_patching.py
            # XXX: Rework this to avoid importing.
            to_import.append(qualified_name)
        else:
            cmd = [sys.executable, '-u']
            if PYPY and PY2:
                # Doesn't seem to be an env var for this
                cmd.extend(('-X', 'track-resources'))
            if package:
                # Using a package is the best way to work with coverage 5
                # when we specify 'source = <package>'
                cmd.append('-m' + qualified_name)
            else:
                cmd.append(filename)

            options = DEFAULT_RUN_OPTIONS.copy()
            options.update(configured_test_options.get(filename, {}))
            to_process.append((cmd, options))

    os.chdir(olddir)
    # When we actually execute, do so from the original directory,
    # this helps find setup.py
    for qualified_name in to_import:
        module = importlib.import_module(qualified_name)
        for cmd, options in module.TESTRUNNER():
            if remove_options(cmd)[-1] in ignore:
                continue
            to_process.append((cmd, options))

    return to_process


def remove_options(lst):
    return [x for x in lst if x and not x.startswith('-')]

def load_list_from_file(filename, package):
    result = []
    if filename:
        with open(_package_relative_filename(filename, package)) as f:
            for x in f:
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
        line = line.replace('FLAKY ', '')
        # Our configs are still mostly written in terms of file names,
        # but the non-monkey tests are now using package names.
        # Strip off '.py' from filenames to see if we match a module.
        # XXX: This could be much better. Our command needs better structure.
        if command.endswith(' ' + line) or command.endswith(line.replace(".py", '')):
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
           configured_failing_tests=(),
           total_cases=0, total_skipped=0):
    # pylint:disable=redefined-builtin,too-many-branches,too-many-locals
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
        log('\n%s/%s unexpected passes', len(passed_unexpected), total, color='error')
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
            log('\n%s/%s unexpected failures', len(failed_unexpected), total, color='error')
            print_list(failed_unexpected)
    else:
        log(
            '\nRan %s tests%s in %s files%s',
            total_cases,
            util._colorize('skipped', " (skipped=%d)" % total_skipped) if total_skipped else '',
            total,
            took,
        )

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

def _setup_environ(debug=False):
    if 'PYTHONWARNINGS' not in os.environ and not sys.warnoptions:

        # action:message:category:module:line
        os.environ['PYTHONWARNINGS'] = ','.join([
            # Enable default warnings such as ResourceWarning.
            'default',
            # On Python 3[.6], the system site.py module has
            # "open(fullname, 'rU')" which produces the warning that
            # 'U' is deprecated, so ignore warnings from site.py
            'ignore:::site:',
            # pkgutil on Python 2 complains about missing __init__.py
            'ignore:::pkgutil',
            # importlib/_bootstrap.py likes to spit out "ImportWarning:
            # can't resolve package from __spec__ or __package__, falling
            # back on __name__ and __path__". I have no idea what that means, but it seems harmless
            # and is annoying.
            'ignore:::importlib._bootstrap:',
            'ignore:::importlib._bootstrap_external:',
            # importing ABCs from collections, not collections.abc
            'ignore:::pkg_resources._vendor.pyparsing:',
        ])

    if 'PYTHONFAULTHANDLER' not in os.environ:
        os.environ['PYTHONFAULTHANDLER'] = 'true'

    if 'GEVENT_DEBUG' not in os.environ and debug:
        os.environ['GEVENT_DEBUG'] = 'debug'

    if 'PYTHONTRACEMALLOC' not in os.environ:
        os.environ['PYTHONTRACEMALLOC'] = '10'

    if 'PYTHONDEVMODE' not in os.environ:
        # Python 3.7
        os.environ['PYTHONDEVMODE'] = '1'

    if 'PYTHONMALLOC' not in os.environ:
        # Python 3.6
        os.environ['PYTHONMALLOC'] = 'debug'



def main():
    # pylint:disable=too-many-locals,too-many-statements
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
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--package", default="gevent.tests")
    parser.add_argument('tests', nargs='*')
    options = parser.parse_args()
    FAILING_TESTS = []
    IGNORED_TESTS = []
    RUN_ALONE = []
    TEST_FILE_OPTIONS = {}

    coverage = False
    if options.coverage or os.environ.get("GEVENTTEST_COVERAGE"):
        coverage = True
        os.environ['COVERAGE_PROCESS_START'] = os.path.abspath(".coveragerc")
        if PYPY:
            os.environ['COVERAGE_PROCESS_START'] = os.path.abspath(".coveragerc-pypy")
        this_dir = os.path.dirname(__file__)
        site_dir = os.path.join(this_dir, 'coveragesite')
        site_dir = os.path.abspath(site_dir)
        os.environ['PYTHONPATH'] = site_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
        # We change directory often, use an absolute path to keep all the
        # coverage files (which will have distinct suffixes because of parallel=true in .coveragerc
        # in this directory; makes them easier to combine and use with coverage report)
        os.environ['COVERAGE_FILE'] = os.path.abspath(".") + os.sep + ".coverage"
        print("Enabling coverage to", os.environ['COVERAGE_FILE'], "with site", site_dir)

    _setup_environ(debug=options.debug)

    if options.config:
        config = {}
        options.config = _package_relative_filename(options.config, options.package)
        with open(options.config) as f:
            config_data = f.read()
        six.exec_(config_data, config)
        FAILING_TESTS = config['FAILING_TESTS']
        IGNORED_TESTS = config['IGNORED_TESTS']
        RUN_ALONE = config['RUN_ALONE']
        TEST_FILE_OPTIONS = config['TEST_FILE_OPTIONS']
        IGNORE_COVERAGE = config['IGNORE_COVERAGE']


    tests = discover(
        options.tests,
        ignore_files=options.ignore,
        ignored=IGNORED_TESTS,
        coverage=coverage,
        package=options.package,
        configured_ignore_coverage=IGNORE_COVERAGE,
        configured_test_options=TEST_FILE_OPTIONS,
    )
    if options.discover:
        for cmd, options in tests:
            print(util.getname(cmd, env=options.get('env'), setenv=options.get('setenv')))
        print('%s tests found.' % len(tests))
    else:
        if PYPY and RESOLVER_ARES:
            # XXX: Add a way to force these.
            print("Not running tests on pypy with c-ares; not a supported configuration")
            return
        if options.package:
            # Put this directory on the path so relative imports work.
            package_dir = _dir_from_package_name(options.package)
            os.environ['PYTHONPATH'] = os.environ.get('PYTHONPATH', "") + os.pathsep + package_dir
        run_many(
            tests,
            configured_failing_tests=FAILING_TESTS,
            failfast=options.failfast,
            quiet=options.quiet,
            configured_run_alone_tests=RUN_ALONE,
        )


if __name__ == '__main__':
    main()
