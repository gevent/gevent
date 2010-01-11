import sys
import os
import glob

modules = []

for path in glob.glob('../examples/*.py'):
    modules.append(path)

assert modules

errors = []

if __name__ == '__main__':

    for path in modules:
        if 'server' in path or path.endswith('proxy.py') or path.endswith('webpy.py'):
            print path, 'skipping'
        else:
            print path, 'running'
            sys.stdout.flush()
            res = os.system('%s %s' % (sys.executable, path))
            if res:
                print path, 'failed'
                errors.append(path)
        print '-----'

    if errors:
        print '\n\nFailures: %s' % ', '.join(errors)
        sys.exit(1)

