from __future__ import with_statement
import gevent
import time
import sys
import os
import threading


class alarm(threading.Thread):
    # can't use signal.alarm because of Windows

    def __init__(self, timeout):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.timeout = timeout
        self.start()

    def run(self):
        time.sleep(self.timeout)
        sys.stderr.write('Timeout.\n')
        os._exit(5)


alarm(1)


with gevent.Timeout(0.01, False):
    while True:
        gevent.sleep(0)
