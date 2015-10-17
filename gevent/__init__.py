# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
"""
gevent is a coroutine-based Python networking library that uses greenlet
to provide a high-level synchronous API on top of libev event loop.

See http://www.gevent.org/ for the documentation.
"""

from __future__ import absolute_import

from collections import namedtuple

_version_info = namedtuple('version_info',
                           ('major', 'minor', 'micro', 'releaselevel', 'serial'))

#: The programatic version identifier. The fields have (roughly) the
#: same meaning as :data:`sys.version_info`
version_info = _version_info(1, 1, 0, 'beta', '6')

#: The human-readable PEP 440 version identifier
__version__ = '1.1b6'


__all__ = ['get_hub',
           'Greenlet',
           'GreenletExit',
           'spawn',
           'spawn_later',
           'spawn_raw',
           'iwait',
           'wait',
           'killall',
           'Timeout',
           'with_timeout',
           'getcurrent',
           'sleep',
           'idle',
           'kill',
           'signal',
           'fork',
           'reinit']


import sys
if sys.platform == 'win32':
    import socket  # trigger WSAStartup call
    del socket

from gevent.hub import get_hub, iwait, wait, PYPY
from gevent.greenlet import Greenlet, joinall, killall
spawn = Greenlet.spawn
spawn_later = Greenlet.spawn_later
from gevent.timeout import Timeout, with_timeout
from gevent.hub import getcurrent, GreenletExit, spawn_raw, sleep, idle, kill, reinit
try:
    from gevent.os import fork
except ImportError:
    __all__.remove('fork')

# See https://github.com/gevent/gevent/issues/648
# A temporary backwards compatibility shim to enable users to continue
# to treat 'from gevent import signal' as a callable, to matter whether
# the 'gevent.signal' module has been imported first
from gevent.hub import signal as _signal_class
from gevent import signal as _signal_module

# The object 'gevent.signal' must:
# - be callable, returning a gevent.hub.signal;
# - answer True to isinstance(gevent.signal(...), gevent.signal);
# - answer True to isinstance(gevent.signal(...), gevent.hub.signal)
# - have all the attributes of the module 'gevent.signal';
# - answer True to isinstance(gevent.signal, types.ModuleType) (optional)

# The only way to do this is to use a metaclass, an instance of which (a class)
# is put in sys.modules and is substituted for gevent.hub.signal.
# This handles everything except the last one.


class _signal_metaclass(type):

    def __getattr__(self, name):
        return getattr(_signal_module, name)

    def __setattr__(self, name, value):
        # Because we can't know whether to try to go to the module
        # or the class, we don't allow setting an attribute after the fact
        raise TypeError("Cannot set attribute")

    def __instancecheck__(self, instance):
        return isinstance(instance, _signal_class)

    def __dir__(self):
        return dir(_signal_module)


class signal(object):

    __doc__ = _signal_module.__doc__

    def __new__(self, *args, **kwargs):
        return _signal_class(*args, **kwargs)


# The metaclass is applied after the class declaration
# for Python 2/3 compatibility
signal = _signal_metaclass(str("signal"),
                           (),
                           dict(signal.__dict__))

sys.modules['gevent.signal'] = signal
sys.modules['gevent.hub'].signal = signal

del sys


# the following makes hidden imports visible to freezing tools like
# py2exe. see https://github.com/gevent/gevent/issues/181
def __dependencies_for_freezing():
    from gevent import core, resolver_thread, resolver_ares, socket,\
        threadpool, thread, threading, select, subprocess
    import pprint
    import traceback
    import signal

del __dependencies_for_freezing

if PYPY:
    # We need to make sure that the CFFI compilation is complete if
    # need be. Without this, we can get ImportError(ImportError:
    # Cannot import 'core' from ...) from the hub or
    # DistutilsModuleError (on OS X) depending on who first imports and inits
    # the hub. See https://github.com/gevent/gevent/issues/619 (There
    # is no automated test for this.)
    from gevent.core import loop
    del loop
