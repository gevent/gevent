import sys
import os
import glob

modules = []

for path in glob.glob('../examples/*.py'):
    modules.append(path)

assert modules

error = 0

for path in modules:
    if path.endswith('server.py'):
        print path, 'skipping'
    else:
        print path, 'running'
        sys.stdout.flush()
        res = os.system('%s %s' % (sys.executable, path))
        if res:
            error = 1
            print path, 'failed'
    print '-----'

if error:
    sys.exit(1)

