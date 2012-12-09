# test for issue #210
from gevent import core
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

log = []
loop = core.loop(default=False)
loop.run_callback(log.append, 1)
loop.run()
assert log == [1], log
