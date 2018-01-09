from __future__ import print_function
import sys

if not sys.argv[1:]:
    from subprocess import Popen, PIPE
    p = Popen([sys.executable, __file__, 'subprocess'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate(b'hello world\n')
    code = p.poll()
    assert p.poll() == 0, (out, err, code)
    assert out.strip() == b'11 chars.', (out, err, code)
    # XXX: This is seen sometimes to fail on Travis with the following value in err but a code of 0;
    # it seems load related:
    #  'Unhandled exception in thread started by \nsys.excepthook is missing\nlost sys.stderr\n'.
    # If warnings are enabled, Python 3 has started producing this:
    # '...importlib/_bootstrap.py:219: ImportWarning: can't resolve package from __spec__
    #    or __package__, falling back on __name__ and __path__\n  return f(*args, **kwds)\n'
    assert err == b'' or b'sys.excepthook' in err or b'ImportWarning' in err, (out, err, code)

elif sys.argv[1:] == ['subprocess']:
    import gevent
    import gevent.monkey
    gevent.monkey.patch_all(sys=True)

    def printline():
        try:
            line = raw_input()
        except NameError:
            line = input()
        print('%s chars.' % len(line))

    gevent.spawn(printline).join()

else:
    sys.exit('Invalid arguments: %r' % (sys.argv, ))
