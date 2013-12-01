# testrunner timeout: 300
import sys
import glob
import subprocess
import time


TIMEOUT = 30


def kill(popen):
    if popen.poll() is not None:
        return
    try:
        popen.kill()
    except OSError as ex:
        if ex.errno == 3:  # No such process
            return
        if ex.errno == 13:  # Permission denied (translated from windows error 5: "Access is denied")
            return
        raise


def wait(popen):
    end = time.time() + TIMEOUT
    while popen.poll() is None:
        if time.time() > end:
            kill(popen)
            popen.wait()
            return 'TIMEOUT'
        time.sleep(0.1)
    return popen.poll()


def system(command):
    popen = subprocess.Popen(command, shell=False)
    try:
        return wait(popen)
    finally:
        kill(popen)


modules = set()

for path in glob.glob('bench_*.py'):
    modules.add(path)

if __name__ == '__main__':
    assert modules

    errors = []

    for path in modules:
        sys.stderr.write(path + '\n')
        sys.stdout.flush()
        command = [sys.executable, '-u', path, 'all']
        res = system(command)
        if res:
            error = '%r failed with %s' % (' '.join(command), res)
            sys.stderr.write(error + '\n')
            errors.append(error)
        sys.stderr.write('-----\n\n')

    if errors:
        sys.exit('\n'.join(errors))
