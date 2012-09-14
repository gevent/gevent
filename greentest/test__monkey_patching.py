import sys
import os
import glob
import subprocess
import time


def wait(popen, timeout=60):
    endtime = time.time() + timeout
    try:
        while True:
            if popen.poll() is not None:
                return popen.poll()
            time.sleep(0.5)
            if time.time() > endtime:
                break
    finally:
        if popen.poll() is None:
            sys.stderr.write('\nKilling %s (timed out)\n' % popen.name)
            try:
                popen.kill()
            except OSError:
                pass
            sys.stderr.write('\n')
    return 'TIMEOUT'


version = '%s.%s.%s' % sys.version_info[:3]
if not os.path.exists(version):
    sys.exit('Directory %s not found in %s' % (version, os.getcwd()))

os.chdir(version)


class ContainsAll(object):
    def __contains__(self, item):
        return True

import test_support
test_support.use_resources = ContainsAll()

total = 0
failed = []

tests = set(glob.glob('test_*.py')) - set(['test_support.py'])
tests = sorted(tests)

for test in tests:
    total += 1
    sys.stderr.write('\nRunning %s\n' % test)
    popen = subprocess.Popen([sys.executable, '-u', '-m', 'monkey_test', test])
    popen.name = test
    if wait(popen):
        failed.append(test)


sys.stderr.write('%s/%s tests failed: %s\n' % (len(failed), total, failed))

if failed:
    sys.exit(1)
