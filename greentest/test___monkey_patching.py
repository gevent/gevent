import sys
import os
import glob
import util
import gevent


TIMEOUT = 120


class ContainsAll(object):
    def __contains__(self, item):
        return True


def TESTRUNNER(tests=None):
    version = '%s.%s.%s' % sys.version_info[:3]
    assert os.path.isdir(version), 'Directory %s not found in %s' % (version, os.getcwd())

    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd() + ':' + os.environ.get('PYTHONPATH', '')

    for filename in glob.glob('%s/@test_*_tmp' % version):
        os.unlink(filename)

    if not tests:
        tests = sorted(glob.glob('%s/test_*.py' % version))

    tests = [os.path.basename(x) for x in tests]
    options = {'cwd': version, 'env': env}

    for filename in tests:
        yield version + '/' + filename, [sys.executable, '-u', '-m', 'monkey_test', filename], options
        yield version + '/' + filename + '/Event', [sys.executable, '-u', '-m', 'monkey_test', '--Event', filename], options


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
