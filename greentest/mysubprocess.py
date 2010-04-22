import sys
import subprocess
from subprocess import *

class Popen(subprocess.Popen):

    if not hasattr(subprocess.Popen, 'kill'):

        def kill(self):
            try:
                from os import kill
                sys.stderr.write('Sending signal 9 to %s\n' % self.pid)
                kill(self.pid, 9)
            except ImportError:
                sys.stderr.write('Cannot kill on this platform. Please kill %s\n' % self.pid)

