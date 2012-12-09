import sys
from gevent.subprocess import Popen
from util import alarm

alarm(1)

popen = Popen([sys.executable, '-c', 'pass'])
while popen.poll() is None:
    pass
