import sys
import os
import glob
import time
import util


cwd = '../examples/'
ignore = ['wsgiserver.py',
          'wsgiserver_ssl.py',
          'webproxy.py',
          'webpy.py',
          'unixsocket_server.py',
          'unixsocket_client.py',
          'psycopg2_pool.py',
          'geventsendfile.py']
ignore += [x[14:] for x in glob.glob('test__example_*.py')]

default_time_range = (2, 4)
time_ranges = {
    'concurrent_download.py': (0, 30),
    'processes.py': (0, 4)}


def main(tests=None):
    if not tests:
        tests = set(os.path.basename(x) for x in glob.glob('../examples/*.py'))
        tests = sorted(tests)

    failed = []

    for filename in tests:
        if filename in ignore:
            continue
        min_time, max_time = time_ranges.get(filename, default_time_range)

        start = time.time()
        if util.run([sys.executable, '-u', filename], timeout=max_time, cwd=cwd):
            failed.append(filename)
        else:
            took = time.time() - start
            if took < min_time:
                util.log('! Failed example %s: exited too quickly, after %.1fs (expected %.1fs)', filename, took, min_time)
                failed.append(filename)

    if failed:
        util.log('! Failed examples:\n! - %s', '\n! - '.join(failed))
        sys.exit(1)

    if not tests:
        sys.exit('No tests.')


if __name__ == '__main__':
    main()
