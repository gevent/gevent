import sys
import os
import glob

import atexit
# subprocess: include in subprocess tests

from greentest import util

TIMEOUT = 120
directory = '%s.%s' % sys.version_info[:2]
full_directory = '%s.%s.%s' % sys.version_info[:3]
if hasattr(sys, 'pypy_version_info'):
    directory += 'pypy'
    full_directory += 'pypy'
version = '%s.%s.%s' % sys.version_info[:3]
if sys.version_info[3] == 'alpha':
    version += 'a%s' % sys.version_info[4]


def get_absolute_pythonpath():
    paths = [os.path.abspath(p) for p in os.environ.get('PYTHONPATH', '').split(os.pathsep)]
    return os.pathsep.join(paths)


def TESTRUNNER(tests=None):
    if not os.path.exists(directory):
        util.log('WARNING: No test directory found at %s', directory)
        return
    with open(os.path.join(directory, 'version')) as f:
        preferred_version = f.read().strip()
    if preferred_version != version:
        util.log('WARNING: The tests in %s/ are from version %s and your Python is %s', directory, preferred_version, version)

    if not tests:
        tests = glob.glob('%s/test_*.py' % directory)
        version_tests = glob.glob('%s/test_*.py' % full_directory)
        tests = sorted(tests)
        version_tests = sorted(version_tests)

    PYTHONPATH = (os.getcwd() + os.pathsep + get_absolute_pythonpath()).rstrip(':')

    tests = [os.path.basename(x) for x in tests]
    version_tests = [os.path.basename(x) for x in version_tests]

    options = {
        'cwd': directory,
        'timeout': TIMEOUT,
        'setenv': {
            'PYTHONPATH': PYTHONPATH,
            'GEVENT_DEBUG': 'error',
        }
    }

    if tests and not sys.platform.startswith("win"):
        atexit.register(os.system, 'rm -f */@test*')

    basic_args = [sys.executable, '-u', '-W', 'ignore', '-m' 'greentest.monkey_test']
    for filename in tests:
        if filename in version_tests:
            util.log("Overriding %s from %s with file from %s", filename, directory, full_directory)
            continue
        yield basic_args + [filename], options.copy()
        yield basic_args + ['--Event', filename], options.copy()

    options['cwd'] = full_directory
    for filename in version_tests:
        yield basic_args + [filename], options.copy()
        yield basic_args + ['--Event', filename], options.copy()


def main():
    from greentest import testrunner
    return testrunner.run_many(list(TESTRUNNER(sys.argv[1:])))


if __name__ == '__main__':
    main()
