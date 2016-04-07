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

orig_saved = {}
for k, v in monkey.saved.items():
    orig_saved[k] = v.copy()

import warnings
with warnings.catch_warnings(record=True) as issued_warnings:
    # Patch again, triggering two warnings, on for os=False/signal=True,
    # one for repeated monkey-patching.
    monkey.patch_all(os=False)
    assert len(issued_warnings) == 2, len(issued_warnings)
    assert 'SIGCHLD' in str(issued_warnings[-1].message), issued_warnings[-1]
    assert 'more than once' in str(issued_warnings[0].message), issued_warnings[0]

    # Patching with the exact same argument doesn't issue a second warning.
    # in fact, it doesn't do anything
    del issued_warnings[:]
    monkey.patch_all(os=False)
    orig_saved['_gevent_saved_patch_all'] = monkey.saved['_gevent_saved_patch_all']

    assert len(issued_warnings) == 0, len(issued_warnings)

# Make sure that re-patching did not change the monkey.saved
# attribute, overwriting the original functions.
assert orig_saved == monkey.saved, (orig_saved, monkey.saved)

# Make sure some problematic attributes stayed correct.
# NOTE: This was only a problem if threading was not previously imported.
for k, v in monkey.saved['threading'].items():
    assert 'gevent' not in str(v), (k, v)
