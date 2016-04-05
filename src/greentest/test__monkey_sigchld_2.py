# Mimics what gunicorn workers do: monkey patch in the child process
# and try to reset signal handlers to SIG_DFL.
# NOTE: This breaks again when gevent.subprocess is used, or any child
# watcher.
import os
import sys

import signal


def handle(*args):
    if not pid:
        # We only do this is the child so our
        # parent's waitpid can get the status.
        # This is the opposite of gunicorn.
        os.waitpid(-1, os.WNOHANG)
# The signal watcher must be installed *before* monkey patching
if hasattr(signal, 'SIGCHLD'):
    signal.signal(signal.SIGCHLD, handle)

    pid = os.fork()

    if pid: # parent
        try:
            _, stat = os.waitpid(pid, 0)
        except OSError:
            # Interrupted system call
            _, stat = os.waitpid(pid, 0)
        assert stat == 0, stat
    else:
        import gevent.monkey
        gevent.monkey.patch_all()
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        # Under Python 2, os.popen() directly uses the popen call, and
        # popen's file uses the pclose() system call to
        # wait for the child. If it's already waited on,
        # it raises the same exception.
        # Python 3 uses the subprocess module directly which doesn't
        # have this problem.
        f = os.popen('true')
        f.close()

        sys.exit(0)
else:
    print("No SIGCHLD, not testing")
