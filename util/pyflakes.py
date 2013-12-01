#!/usr/bin/python
import sys
import re
import subprocess


IGNORED = r'''
gevent/socket.py:\d+: undefined name
gevent/socket.py:\d+: 'sslerror' imported but unused
gevent/socket.py:\d+: 'SSLType' imported but unused
gevent/socket.py:\d+: 'ssl' imported but unused
gevent/subprocess.py:\d+: undefined name
gevent/ssl.py:\d+: undefined name
gevent/__init__.py:\d+:.*imported but unused
gevent/__init__.py:\d+: redefinition of unused 'signal' from line
gevent/coros.py:\d+: 'from gevent.lock import *' used; unable to detect undefined names
gevent/coros.py:\d+: '__all__' imported but unused
gevent/thread.py:\d+: '_local' imported but unused
gevent/threading.py:\d+: '\w+' imported but unused
gevent/wsgi.py:1: 'from gevent.pywsgi import *' used; unable to detect undefined names
examples/webchat/urls.py:1: 'from django.conf.urls.defaults import *' used; unable to detect undefined names
greentest/test__queue.py:\d+: undefined name 'GenericGetTestCase'
greentest/test__server_pywsgi.py:
'''

IGNORED = IGNORED.strip().replace(' *', ' \\*').split('\n')


def is_ignored(line):
    for pattern in IGNORED:
        if re.match(pattern, line):
            return True


popen = subprocess.Popen('%s `which pyflakes` gevent/ examples/ greentest/*.py util/ *.py' % sys.executable,
                         shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
output, errors = popen.communicate()

if errors:
    sys.stderr.write(errors.decode())

if popen.poll() != 1:
    sys.stderr.write(output + '\n')
    sys.exit('pyflakes returned %r' % popen.poll())

if errors:
    sys.exit(1)

assert output

output = output.strip().split('\n')
failed = False


for line in output:
    line = line.strip()
    if not is_ignored(line):
        print 'E %s' % line
        failed = True
    #else:
    #    print 'I %s' % line

if failed:
    sys.exit(1)
