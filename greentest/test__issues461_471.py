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
    from subprocess import Popen, PIPE, TimeoutExpired
    if sys.platform.startswith('win'):
        from subprocess import CREATE_NEW_PROCESS_GROUP
        kwargs = {'creationflags': CREATE_NEW_PROCESS_GROUP}
    else:
        kwargs = {}
    p = Popen([sys.executable, __file__, 'subprocess'], stdout=PIPE, **kwargs)
    p.stdout.readline()
    p.send_signal(signal.SIGINT)
    try:
        p.wait(3)
    except TimeoutExpired:
        p.terminate()
        sys.exit(1)
    sys.exit(p.returncode)
