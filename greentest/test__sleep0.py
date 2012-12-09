from __future__ import with_statement
import gevent
from util import alarm


alarm(1)


with gevent.Timeout(0.01, False):
    while True:
        gevent.sleep(0)
