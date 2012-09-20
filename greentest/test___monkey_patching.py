import sys
import os
import glob
import util
import gevent


TIMEOUT = 120


def TESTRUNNER(tests=None):
    directory = '%s.%s' % sys.version_info[:2]
    version = '%s.%s.%s' % sys.version_info[:3]
    preferred_version = open(os.path.join(directory, 'version')).read().strip()
    if preferred_version != version:
        util.log('WARNING: The tests in %s/ are from version %s and your Python is %s', directory, preferred_version, version)

    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd() + ':' + os.environ.get('PYTHONPATH', '')

    for filename in glob.glob('%s/@test_*_tmp' % directory):
        os.unlink(filename)

    if not tests:
        tests = sorted(glob.glob('%s/test_*.py' % directory))

    tests = [os.path.basename(x) for x in tests]
    options = {'cwd': directory, 'env': env}

    for filename in tests:
        yield directory + '/' + filename, [sys.executable, '-u', '-m', 'monkey_test', filename], options
        yield directory + '/' + filename + '/Event', [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options


def main():
    from testrunner import pool
    import time
    failed = []
    def run(name, cmd, **kwargs):
        if util.run(cmd, **kwargs):
            failed.append(name)
    start = time.time()
    total = 0
    for name, cmd, options in TESTRUNNER(sys.argv[1:]):
        total += 1
        pool.spawn(run, name, cmd, **options)
    gevent.run()
    util.report(total, failed, took=time.time()-start)


if __name__ == '__main__':
    main()
