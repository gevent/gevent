'''Test for GitHub issues 461 and 471.

When moving to Python 3, handling of KeyboardInterrupt exceptions caused
by a Ctrl-C raise an exception while printing the traceback for a
greenlet preventing the process from exiting. This test tests for proper
handling of KeyboardInterrupt.
'''

import sys

if sys.argv[1:] == ['subprocess']:
    import gevent

    def task():
        sys.stdout.write('ready\n')
        sys.stdout.flush()
        gevent.sleep(30)
    try:
        gevent.spawn(task).get()
    except KeyboardInterrupt:
        pass
else:
    import signal
    from subprocess import Popen, PIPE
    import time

    if sys.platform.startswith('win'):
        from subprocess import CREATE_NEW_PROCESS_GROUP
        kwargs = {'creationflags': CREATE_NEW_PROCESS_GROUP}
    else:
        kwargs = {}
    p = Popen([sys.executable, __file__, 'subprocess'], stdout=PIPE, **kwargs)
    line = p.stdout.readline()
    if not isinstance(line, str):
        line = line.decode('ascii')
    assert line == 'ready\n'
    p.send_signal(signal.SIGINT)
    # Wait up to 3 seconds for child process to die
    for i in range(30):
        if p.poll() is not None:
            break
        time.sleep(0.1)
    else:
        # Kill unresponsive child and exit with error 1
        p.terminate()
        p.wait()
        sys.exit(1)
    sys.exit(p.returncode)
