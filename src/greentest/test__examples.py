import sys
import os
import glob
import time

import greentest
from greentest import util


cwd = '../../examples/'
ignore = [
    'wsgiserver.py',
    'wsgiserver_ssl.py',
    'webproxy.py',
    'webpy.py',
    'unixsocket_server.py',
    'unixsocket_client.py',
    'psycopg2_pool.py',
    'geventsendfile.py',
]
ignore += [x[14:] for x in glob.glob('test__example_*.py')]

default_time_range = (2, 4)
time_ranges = {
    'concurrent_download.py': (0, 30),
    'processes.py': (0, 4)
}

class _AbstractTestMixin(object):
    time_range = (2, 4)
    filename = None

    def test_runs(self):
        start = time.time()
        min_time, max_time = self.time_range
        if util.run([sys.executable, '-u', self.filename],
                    timeout=max_time,
                    cwd=cwd,
                    quiet=True,
                    buffer_output=True,
                    nested=True,
                    setenv={'GEVENT_DEBUG': 'error'}):
            self.fail("Failed example: " + self.filename)
        else:
            took = time.time() - start
            self.assertGreaterEqual(took, min_time)

for filename in glob.glob(cwd + '/*.py'):
    bn = os.path.basename(filename)
    if bn in ignore:
        continue
    tc = type('Test_' + bn,
              (_AbstractTestMixin, greentest.TestCase),
              {
                  'filename': bn,
                  'time_range': time_ranges.get(bn, _AbstractTestMixin.time_range)
              })
    locals()[tc.__name__] = tc

if __name__ == '__main__':
    greentest.main()
