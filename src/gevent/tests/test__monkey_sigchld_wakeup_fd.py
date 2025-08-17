import gevent.monkey

gevent.monkey.patch_all()

import sys

# Try to produce output compatible with unittest output so
# our status parsing functions work.

import signal
# pylint:disable=no-member,unused-argument
if hasattr(signal, 'SIGCHLD'):
    from gevent import Timeout
    from gevent.os import make_nonblocking, nb_read
    from signal import SIGCHLD, set_wakeup_fd, signal
    import os
    import subprocess

    pipe_r, pipe_w = os.pipe()
    make_nonblocking(pipe_r)
    make_nonblocking(pipe_w)


    def signal_handler(signum, frame):
        pass


    signal(SIGCHLD, signal_handler)
    set_wakeup_fd(pipe_w, warn_on_full_buffer=True)

    with subprocess.Popen([sys.executable, "-c", "pass"]) as proc:
        pass

    with Timeout(5):
        read_signals = nb_read(pipe_r, 65535)
        assert read_signals == bytes((SIGCHLD.value,))

    print("Ran 1 tests in 0.0s")
    sys.exit(0)
else:
    print("No SIGCHLD, not testing")
    print("Ran 1 tests in 0.0s (skipped=1)")
