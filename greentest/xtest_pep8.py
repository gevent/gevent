import sys
import os


if os.system('pep8 --version'):
    sys.exit('ERROR: pep8 script not found')


if not os.path.exists('gevent') and not os.path.exists('setup.py'):
    os.chdir('..')


commands = [
    'pep8 --show-source --max-line-length=160 gevent/ setup.py',
    'pep8 --show-source --max-line-length=160 --ignore E702 examples/*.py',
    'pep8 --show-source --max-line-length=160 --ignore E702,E128 examples/webchat',
    'pep8 --show-source --max-line-length=160 doc/']


failures = 0
for command in commands:
    if os.system(command):
        failures += 1


sys.exit(failures)
