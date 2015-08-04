#!/usr/bin/env python
from __future__ import print_function
import sys
import re
import subprocess
import glob


IGNORED = r'''
gevent/socket.py:\d+: undefined name
gevent/_socket[23].py:\d+: undefined name
gevent/_socketcommon.py:\d+: undefined name
gevent/_socketcommon.py:\d+: .*imported but unused
gevent/subprocess.py:\d+: undefined name
gevent/_?ssl[23]?.py:\d+: undefined name
gevent/__init__.py:\d+:.*imported but unused
gevent/__init__.py:\d+: redefinition of unused 'signal' from line
gevent/__init__.py:\d+: redefinition of unused 'socket' from line
gevent/coros.py:\d+: 'from gevent.lock import *' used; unable to detect undefined names
gevent/coros.py:\d+: '__all__' imported but unused
gevent/hub.py:\d+: 'reraise' imported but unused
gevent/thread.py:\d+: '_local' imported but unused
gevent/threading.py:\d+: '\w+' imported but unused
gevent/wsgi.py:1: 'from gevent.pywsgi import *' used; unable to detect undefined names
examples/webchat/urls.py:1: 'from django.conf.urls.defaults import *' used; unable to detect undefined names
greentest/test__queue.py:\d+: undefined name 'GenericGetTestCase'
greentest/test__server_pywsgi.py:
gevent/core.py:\d+: 'from gevent.corecffi import *' used; unable to detect undefined names
gevent/core.py:\d+: 'from gevent.corecext import *' used; unable to detect undefined names
gevent/_sslgte279.py:.*
gevent/os.py:\d+: redefinition of unused 'fork' from line
'''

IGNORED = IGNORED.strip().replace(' *', ' \\*').split('\n')


def is_ignored(line):
    for pattern in IGNORED:
        if re.match(pattern, line):
            return True


def pyflakes(args):
    popen = subprocess.Popen('%s `which pyflakes` %s' % (sys.executable, args),
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

    output = output.decode('utf-8')
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


pyflakes('examples/ greentest/*.py util/ *.py')

if sys.version_info[0] == 3:
    ignored_files = ['gevent/_util_py2.py', 'gevent/_socket2.py', 'gevent/_fileobject2.py',
                     'gevent/builtins.py']
else:
    ignored_files = ['gevent/_socket3.py']

ignored_files.append('gevent/wsgi.py')

py = set(glob.glob('gevent/*.py')) - set(ignored_files)
pyflakes(' '.join(py))
