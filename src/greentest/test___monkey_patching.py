import sys
import os
import glob
import util
import atexit
# subprocess: include in subprocess tests


TIMEOUT = 120
directory = '%s.%s' % sys.version_info[:2]
full_directory = '%s.%s.%s' % sys.version_info[:3]
if hasattr(sys, 'pypy_version_info'):
    directory += 'pypy'
    full_directory += 'pypy'
version = '%s.%s.%s' % sys.version_info[:3]


def get_absolute_pythonpath():
    paths = [os.path.abspath(p) for p in os.environ.get('PYTHONPATH', '').split(os.pathsep)]
    return os.pathsep.join(paths)


def TESTRUNNER(tests=None):
    if not os.path.exists(directory):
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

    options = {'cwd': directory,
               'timeout': TIMEOUT,
               'setenv': {'PYTHONPATH': PYTHONPATH}}

    if tests:
        atexit.register(os.system, 'rm -f */@test*')

    for filename in tests:
        if filename in version_tests:
            util.log("Overriding %s from %s with file from %s", filename, directory, full_directory)
            continue
        yield [sys.executable, '-u', '-m', 'monkey_test', filename], options.copy()
        yield [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options.copy()

    options['cwd'] = full_directory
    for filename in version_tests:
        yield [sys.executable, '-u', '-m', 'monkey_test', filename], options.copy()
        yield [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options.copy()


def main():
    import testrunner
    return testrunner.run_many(list(TESTRUNNER(sys.argv[1:])))


if __name__ == '__main__':
    main()
