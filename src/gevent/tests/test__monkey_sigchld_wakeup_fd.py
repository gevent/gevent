import gevent.monkey

gevent.monkey.patch_all()

import signal
import sys

# Try to produce output compatible with unittest output so
# our status parsing functions work.

if hasattr(signal, 'SIGCHLD'):
    import os
    import subprocess
    from signal import SIGCHLD
    from signal import set_wakeup_fd
    from signal import signal

    from gevent import Timeout
    from gevent.os import make_nonblocking
    from gevent.os import nb_read

    pipe_r, pipe_w = os.pipe()
    make_nonblocking(pipe_r)
    make_nonblocking(pipe_w)


    def signal_handler(_signum, _frame):
        pass


    signal(SIGCHLD, signal_handler)
    set_wakeup_fd(pipe_w, warn_on_full_buffer=True)

    with subprocess.Popen([sys.executable, "-c", "pass"]) as proc:
        pass

    with Timeout(5):
        read_signals = nb_read(pipe_r, 65535)
        if read_signals != bytes((SIGCHLD.value,)): # pylint: disable=no-member
            raise AssertionError(read_signals)

    print("Ran 1 tests in 0.0s")
    sys.exit(0)
else:
    print("No SIGCHLD, not testing")
    print("Ran 1 tests in 0.0s (skipped=1)")
