import sys
import os
import subprocess
import signal
from subprocess import PIPE, STDOUT


class Popen(subprocess.Popen):

    def send_signal(self, sig):
        if sys.platform == 'win32':
            sig = signal.SIGTERM
        if hasattr(subprocess.Popen, 'send_signal'):
            try:
                return subprocess.Popen.send_signal(self, sig)
            except Exception, ex:
                sys.stderr.write('send_signal(%s, %s) failed: %s\n' % (self.pid, sig, ex))
                self.external_kill(str(ex))
        else:
            if hasattr(os, 'kill'):
                sys.stderr.write('Sending signal %s to %s\n' % (sig, self.pid))
                try:
                    os.kill(self.pid, sig)
                except Exception, ex:
                    sys.stderr.write('Error while killing %s: %s\n' % (self.pid, ex))
                    self.external_kill()
            else:
                self.external_kill()

    if not hasattr(subprocess.Popen, 'kill'):

        def kill(self):
            return self.send_signal(getattr(signal, 'SIGTERM', 15))

    if not hasattr(subprocess.Popen, 'terminate'):

        def terminate(self):
            return self.send_signal(getattr(signal, 'SIGTERM', 9))

    def interrupt(self):
        sig = getattr(signal, 'SIGINT', 2)
        return self.send_signal(sig)

    def external_kill(self, reason=''):
        if sys.platform == 'win32':
            sys.stderr.write('Killing %s: %s\n' % (self.pid, reason))
            os.system('taskkill /f /pid %s' % self.pid)
        else:
            sys.stderr.write('Cannot kill on this platform. Please kill %s\n' % self.pid)
