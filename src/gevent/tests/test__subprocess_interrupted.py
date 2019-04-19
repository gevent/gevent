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
        # We've seen three. unexpected forms out output.
        #
        # The first involves 'refs'; I don't remember what that was
        # about, but I think it had to do with debug builds of Python.
        #
        # The second is the classic "Unhandled exception in thread
        # started by \nsys.excepthook is missing\nlost sys.stderr".
        # This is a race condition between closing sys.stderr and
        # writing buffered data to a pipe that hasn't been read. We
        # only see this using GEVENT_FILE=thread (which makes sense).
        #
        # The third is similar to the second: "AssertionError:
        # ...\nIOError: close() called during concurrent operation on
        # the same file object.\n"
        if b'refs' in err or b'sys.excepthook' in err or b'concurrent' in err:
            assert err.startswith(b'bye'), repr(err) # pragma: no cover
        else:
            assert err.strip() == b'bye', repr(err)
