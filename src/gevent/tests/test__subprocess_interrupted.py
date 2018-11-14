import sys

if 'runtestcase' in sys.argv[1:]: # pragma: no cover
    import gevent
    import gevent.subprocess
    gevent.spawn(sys.exit, 'bye')
    # Look closely, this doesn't actually do anything, that's a string
    # not a division
    gevent.subprocess.Popen([sys.executable, '-c', '"1/0"'])
    gevent.sleep(1)
else:
    import subprocess
    for _ in range(5):
        out, err = subprocess.Popen([sys.executable, '-W', 'ignore',
                                     __file__, 'runtestcase'],
                                    stderr=subprocess.PIPE).communicate()
        if b'refs' in err: # Something to do with debug mode python builds?
            assert err.startswith(b'bye'), repr(err) # pragma: no cover
        else:
            assert err.strip() == b'bye', repr(err)
