import os
import sys
import gevent
import subprocess

if sys.argv[1:] == []:
    os.environ['GEVENT_BACKEND'] = 'select'
    popen = subprocess.Popen([sys.executable, 'test__environ.py', '1'])
    assert popen.wait() == 0, popen.poll()
else:
    hub = gevent.get_hub()
    assert hub.loop.backend == 'select', hub.loop.backend
