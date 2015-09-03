import errno
import os
import sys
#os.environ['GEVENT_NOWAITPID'] = 'True'

import gevent
import gevent.monkey
gevent.monkey.patch_all()

pid = None
awaiting_child = [True]


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

    pid = os.fork()
    if not pid:
        # child
        gevent.sleep(0.2)
        sys.exit(0)
    else:
        with gevent.Timeout(1):
            while awaiting_child:
                gevent.sleep(0.01)
            # We should now be able to waitpid() for an arbitrary child
            wpid, status = os.waitpid(-1, os.WNOHANG)
            assert wpid == pid
            # And a second call should raise ECHILD
            try:
                wpid, status = os.waitpid(-1, os.WNOHANG)
                raise AssertionError("Should not be able to wait again")
            except OSError as e:
                assert e.errno == errno.ECHILD
            sys.exit(0)
else:
    print("No SIGCHLD, not testing")
