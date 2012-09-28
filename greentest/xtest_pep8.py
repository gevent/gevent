import sys
import os


sys.stderr.write('pep8 --version: ')
if os.system('pep8 --version'):
    sys.exit('ERROR: pep8 script not found')


if not os.path.exists('gevent') and not os.path.exists('setup.py'):
    os.chdir('..')


commands = [
    'pep8 --show-source --max-line-length=160 gevent/ setup.py',
    'pep8 --show-source --max-line-length=160 --ignore E702 examples/*.py',
    'pep8 --show-source --max-line-length=160 --ignore E702,E128 examples/webchat',
    'pep8 --show-source --max-line-length=160 doc/',
    "pep8 --max-line-length=200 --exclude 'test_support.py,test_queue.py,lock_tests.py,patched_tests_setup.py,test_threading_2.py' --ignore E702 greentest/*.py",
    'pep8 --show-source --max-line-length=160 --ignore E203,E128,E124,E201 greentest/patched_tests_setup.py']

failures = 0
for command in commands:
    sys.stderr.write('+ %s\n' % command)
    if os.system(command):
        failures += 1


sys.exit(failures)
