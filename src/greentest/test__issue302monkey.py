import sys


if 'gevent' not in sys.modules:
    from subprocess import Popen
    args = [sys.executable, '-m', 'gevent.monkey', __file__]
    p = Popen(args)
    code = p.wait()
    assert code == 0, code

else:
    import socket
    assert 'gevent' in repr(socket.socket), repr(socket.socket)
    assert __file__ == 'test__issue302monkey.py', repr(__file__)
    assert __package__ is None, __package__
