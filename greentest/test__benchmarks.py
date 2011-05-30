import sys
import glob
import mysubprocess as subprocess
import time


TIMEOUT = 10

def system(command):
    p = subprocess.Popen(command, shell=True)
    try:
        start = time.time()
        while time.time() < start + TIMEOUT and p.poll() is None:
            time.sleep(0.1)
        if p.poll() is None:
            p.kill()
            return 'KILLED'
        return p.poll()
    finally:
        if p.poll() is None:
            p.kill()


modules = set()

for path in glob.glob('bench_*.py'):
    modules.add(path)

if __name__ == '__main__':
    assert modules

    errors = []

    for path in modules:
        sys.stderr.write(path + '\n')
        sys.stdout.flush()
        command = '%s %s all' % (sys.executable, path)
        res = system(command)
        if res:
            error = '%r failed with code %s' % (command, res)
            sys.stderr.write(error + '\n')
            errors.append(error)
        sys.stderr.write('-----\n\n')

    if errors:
        sys.exit('\n'.join(errors))
