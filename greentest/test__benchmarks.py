import sys
import os
import glob

modules = set()

for path in glob.glob('bench_*.py'):
    modules.add(path)

assert modules

error = 0

if __name__ == '__main__':

    for path in modules:
        print path
        sys.stdout.flush()
        res = os.system('%s %s all' % (sys.executable, path))
        if res:
            error = 1
            print path, 'failed'
        print '-----'

    if error:
        sys.exit(1)

