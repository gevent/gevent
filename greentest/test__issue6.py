from __future__ import print_function
import sys


if not sys.argv[1:]:
    from subprocess import Popen, PIPE
    p = Popen([sys.executable, __file__, 'subprocess'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate('hello world\n')
    code = p.poll()
    assert p.poll() == 0, (out, err, code)
    assert out.strip() == '11 chars.', (out, err, code)
    assert err == '', (out, err, code)

elif sys.argv[1:] == ['subprocess']:
    import gevent
    import gevent.monkey
    gevent.monkey.patch_all(sys=True)

    def printline():
        line = raw_input()
        print('%s chars.' % len(line))

    gevent.spawn(printline).join()

else:
    sys.exit('Invalid arguments: %r' % (sys.argv, ))
