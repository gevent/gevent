# Mimics what gunicorn workers do *if* the arbiter is also monkey-patched:
# After forking from the master monkey-patched process, the child
# resets signal handlers to SIG_DFL. If we then fork and watch *again*,
# we shouldn't hang. (Note that we carefully handle this so as not to break
# os.popen)
from __future__ import print_function
# Patch in the parent process.
import gevent.monkey
gevent.monkey.patch_all()

from gevent import get_hub

import os
import sys

import signal
import subprocess

def _waitpid(pid):
    try:
        _, stat = os.waitpid(pid, 0)
    except OSError:
        # Interrupted system call
        _, stat = os.waitpid(pid, 0)
    assert stat == 0, stat

if hasattr(signal, 'SIGCHLD'):
    # Do what subprocess does and make sure we have the watcher
    # in the parent
    get_hub().loop.install_sigchld()


    pid = os.fork()

    if pid: # parent
        _waitpid(pid)
    else:
        # Child resets.
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

        # Go through subprocess because we expect it to automatically
        # set up the waiting for us.
        popen = subprocess.Popen([sys.executable, '-c', 'import sys'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        popen.stderr.read()
        popen.stdout.read()
        popen.wait() # This hangs if it doesn't.


        sys.exit(0)
else:
    print("No SIGCHLD, not testing")
