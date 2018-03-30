from __future__ import print_function
import socket
import sys
if sys.argv[1] == 'patched':
    print('gevent' in repr(socket.socket))
else:
    assert sys.argv[1] == 'stdlib'
    print('gevent' not in repr(socket.socket))
print(__file__)

if sys.version_info[:2] == (2, 7):
    print(__package__ == None)
else:
    if sys.argv[1] == 'patched':
        # __package__ is handled differently, for some reason,
        # and runpy doesn't let us override it. When we call it,
        # it becomes ''
        print(__package__ == '')
    else:
        # but the interpreter sets it to None
        print(__package__ == None)
