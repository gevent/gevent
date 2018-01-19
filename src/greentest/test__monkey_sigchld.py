import errno
import os
import sys
#os.environ['GEVENT_NOWAITPID'] = 'True'

import gevent
import gevent.monkey
gevent.monkey.patch_all()

pid = None
awaiting_child = []


def handle_sigchld(*args):
    # Make sure we can do a blocking operation
    gevent.sleep()
    # Signal completion
    awaiting_child.pop()
    # Raise an ignored error
    raise TypeError("This should be ignored but printed")

import signal
if hasattr(signal, 'SIGCHLD'):
    assert signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL
    signal.signal(signal.SIGCHLD, handle_sigchld)
    handler = signal.getsignal(signal.SIGCHLD)
    assert signal.getsignal(signal.SIGCHLD) is handle_sigchld, handler

    if hasattr(os, 'forkpty'):
        def forkpty():
            # For printing in errors
            return os.forkpty()[0]
        funcs = (os.fork, forkpty)
    else:
        funcs = (os.fork,)

    for func in funcs:
        awaiting_child = [True]
        pid = func()
        if not pid:
            # child
            gevent.sleep(0.3)
            sys.exit(0)
        else:
            timeout = gevent.Timeout(1)
            try:
                while awaiting_child:
                    gevent.sleep(0.01)
                # We should now be able to waitpid() for an arbitrary child
                wpid, status = os.waitpid(-1, os.WNOHANG)
                if wpid != pid:
                    raise AssertionError("Failed to wait on a child pid forked with a function",
                                         wpid, pid, func)

                # And a second call should raise ECHILD
                try:
                    wpid, status = os.waitpid(-1, os.WNOHANG)
                    raise AssertionError("Should not be able to wait again")
                except OSError as e:
                    assert e.errno == errno.ECHILD
            except gevent.Timeout as t:
                if timeout is not t:
                    raise
                raise AssertionError("Failed to wait using", func)
            finally:
                timeout.close()
    sys.exit(0)
else:
    print("No SIGCHLD, not testing")
