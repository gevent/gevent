import sys
import os
import glob
import util
import atexit

BASEDIR = os.path.abspath(os.path.dirname(__file__))

TIMEOUT = 60
directory = '%s.%s' % sys.version_info[:2]
version = '%s.%s.%s' % sys.version_info[:3]


def TESTRUNNER(tests=None):
    preferred_version = open(os.path.join(directory, 'version')).read().strip()
    if preferred_version != version:
        util.log('WARNING: The tests in %s/ are from version %s and your Python is %s', directory, preferred_version, version)

    if not tests:
        tests = sorted(glob.glob('%s/test_*.py' % directory))

    paths = [ BASEDIR ]

    # resolve relative paths now, because we're going to call the subproccess
    # with a different working directory
    paths.extend( os.path.abspath(p) for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) )
    PYTHONPATH = os.pathsep.join(paths)

    tests = [os.path.basename(x) for x in tests]
    options = {'cwd': directory,
               'timeout': TIMEOUT,
               'setenv': {'PYTHONPATH': PYTHONPATH}}

    if tests:
        atexit.register(os.system, 'rm -f */@test*')

    for filename in tests:
        yield [sys.executable, '-u', '-m', 'monkey_test', filename], options.copy()
        yield [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options.copy()


def main():
    import testrunner
    return testrunner.run_many(list(TESTRUNNER(sys.argv[1:])))


if __name__ == '__main__':
    main()
