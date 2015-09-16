from gevent import monkey
monkey.patch_all()
import sys

import time
assert 'built-in' not in repr(time.sleep), repr(time.sleep)

try:
    import thread
except ImportError:
    import _thread as thread
import threading
assert 'built-in' not in repr(thread.start_new_thread), repr(thread.start_new_thread)
assert 'built-in' not in repr(threading._start_new_thread), repr(threading._start_new_thread)
if sys.version_info[0] == 2:
    assert 'built-in' not in repr(threading._sleep), repr(threading._sleep)

import socket
from gevent import socket as gevent_socket
assert socket.create_connection is gevent_socket.create_connection

import os
import types
for name in ('fork', 'forkpty'):
    if hasattr(os, name):
        attr = getattr(os, name)
        assert 'built-in' not in repr(attr), repr(attr)
        assert not isinstance(attr, types.BuiltinFunctionType), repr(attr)
        assert isinstance(attr, types.FunctionType), repr(attr)

assert monkey.saved

assert not monkey.is_object_patched('threading', 'Event')
monkey.patch_thread(Event=True)
assert monkey.is_object_patched('threading', 'Event')

for modname in monkey.saved:
    assert monkey.is_module_patched(modname)

    for objname in monkey.saved[modname]:
        assert monkey.is_object_patched(modname, objname)
