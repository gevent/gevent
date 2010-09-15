import sys
import glob
import mysubprocess as subprocess
import time


def system(command):
    p = subprocess.Popen(command, shell=True)
    try:
        start = time.time()
        while time.time() < start + 10 and p.poll() is None:
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

assert modules

error = 0

if __name__ == '__main__':

    for path in modules:
        print path
        sys.stdout.flush()
        res = system('%s %s all' % (sys.executable, path))
        if res:
            error = 1
            print path, 'failed'
        print '-----'

    if error:
        sys.exit(1)
