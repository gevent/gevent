import sys
import os
import glob
import time
import unittest

import gevent.testing as greentest
from gevent.testing import util

this_dir = os.path.dirname(__file__)

def _find_files_to_ignore():
    old_dir = os.getcwd()
    try:
        os.chdir(this_dir)

        result = [
            'wsgiserver.py',
            'wsgiserver_ssl.py',
            'webproxy.py',
            'webpy.py',
            'unixsocket_server.py',
            'unixsocket_client.py',
            'psycopg2_pool.py',
            'geventsendfile.py',
        ]
        if greentest.PYPY and greentest.RUNNING_ON_APPVEYOR:
            # For some reason on Windows with PyPy, this times out,
            # when it should be very fast.
            result.append("processes.py")
        result += [x[14:] for x in glob.glob('test__example_*.py')]

    finally:
        os.chdir(old_dir)

    return result

default_time_range = (2, 4)
time_ranges = {
    'concurrent_download.py': (0, 30),
    'processes.py': (0, 4)
}

class _AbstractTestMixin(util.ExampleMixin):
    time_range = (2, 4)
    filename = None

    def test_runs(self):
        start = time.time()
        min_time, max_time = self.time_range
        if not util.run([sys.executable, '-u', self.filename],
                        timeout=max_time,
                        cwd=self.cwd,
                        quiet=True,
                        buffer_output=True,
                        nested=True,
                        setenv={'GEVENT_DEBUG': 'error'}):
            self.fail("Failed example: " + self.filename)
        else:
            took = time.time() - start
            self.assertGreaterEqual(took, min_time)

def _build_test_classes():
    result = {}
    try:
        example_dir = util.ExampleMixin().cwd
    except unittest.SkipTest:
        util.log("WARNING: No examples dir found", color='suboptimal-behaviour')
        return result

    ignore = _find_files_to_ignore()
    for filename in glob.glob(example_dir + '/*.py'):
        bn = os.path.basename(filename)
        if bn in ignore:
            continue
        tc = type(
            'Test_' + bn,
            (_AbstractTestMixin, greentest.TestCase),
            {
                'filename': bn,
                'time_range': time_ranges.get(bn, _AbstractTestMixin.time_range)
            }
        )
        result[tc.__name__] = tc
    return result

for k, v in _build_test_classes().items():
    locals()[k] = v

if __name__ == '__main__':
    greentest.main()
