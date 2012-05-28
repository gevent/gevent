import sys
import os


if 'runtestcase' in sys.argv[1:]:
    import gevent
    import gevent.subprocess
    gevent.spawn(sys.exit, 'bye')
    gevent.subprocess.Popen('python -c "1/0"'.split())
    gevent.sleep(1)
else:
    import subprocess
    for _ in xrange(5):
        out, err = subprocess.Popen([sys.executable, __file__, 'runtestcase'], stderr=subprocess.PIPE).communicate()
        assert err.strip() == 'bye', err
