import sys
import os
import glob
import util


TIMEOUT = 120
directory = '%s.%s' % sys.version_info[:2]
version = '%s.%s.%s' % sys.version_info[:3]


def TESTRUNNER(tests=None):
    preferred_version = open(os.path.join(directory, 'version')).read().strip()
    if preferred_version != version:
        util.log('WARNING: The tests in %s/ are from version %s and your Python is %s', directory, preferred_version, version)

    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd() + ':' + os.environ.get('PYTHONPATH', '')

    if not tests:
        tests = sorted(glob.glob('%s/test_*.py' % directory))

    tests = [os.path.basename(x) for x in tests]
    options = {'cwd': directory, 'env': env}

    for filename in tests:
        yield directory + '/' + filename, [sys.executable, '-u', '-m', 'monkey_test', filename], options
        yield directory + '/' + filename + '/Event', [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options


def main():
    import testrunner
    return testrunner.run_many(TESTRUNNER())


if __name__ == '__main__':
    main()
