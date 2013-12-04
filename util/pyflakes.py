#!/usr/bin/python
from __future__ import print_function
import sys
import re
import subprocess


IGNORED = r'''
gevent/socket.py:\d+: undefined name
gevent/subprocess.py:\d+: undefined name
gevent/ssl.py:\d+: undefined name
gevent/__init__.py:\d+:.*imported but unused
gevent/__init__.py:\d+: redefinition of unused 'signal' from line
gevent/coros.py:\d+: 'from gevent.lock import *' used; unable to detect undefined names
gevent/coros.py:\d+: '__all__' imported but unused
gevent/subprocess.py:\d+: redefinition of unused 'rawlink' from line 311
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


popen = subprocess.Popen('pyflakes gevent/ examples/ greentest/*.py util/ *.py', shell=True, stdout=subprocess.PIPE)
output, _err = popen.communicate()
if popen.poll() != 1:
    sys.stderr.write(output + '\n')
    sys.exit('pyflakes returned %r' % popen.poll())

assert output

output = output.strip().split('\n')
failed = False


for line in output:
    line = line.strip()
    if not is_ignored(line):
        print('E %s' % line)
        failed = True
    #else:
    #    print('I %s' % line)

if failed:
    sys.exit(1)
