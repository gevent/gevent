# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
"""
gevent is a coroutine-based Python networking library that uses greenlet
to provide a high-level synchronous API on top of libevent event loop.

See http://www.gevent.org/ for the documentation.
"""

version_info = (0, 14, 0)
__version__ = '0.14.0dev'

__all__ = ['get_hub',
           'Greenlet',
           'GreenletExit',
           'spawn',
           'spawn_later',
           'spawn_link',
           'spawn_link_value',
           'spawn_link_exception',
           'spawn_raw',
           'joinall',
           'killall',
           'Timeout',
           'with_timeout',
           'getcurrent',
           'sleep',
           'kill',
           'signal',
           'fork',
           'core',
           'reinit']


import sys
if sys.platform == 'win32':
    __import__('socket')  # trigger WSAStartup call
del sys


from gevent import core
from gevent.greenlet import Greenlet, joinall, killall
spawn = Greenlet.spawn
spawn_later = Greenlet.spawn_later
spawn_link = Greenlet.spawn_link
spawn_link_value = Greenlet.spawn_link_value
spawn_link_exception = Greenlet.spawn_link_exception
from gevent.timeout import Timeout, with_timeout
from gevent.hub import getcurrent, GreenletExit, spawn_raw, sleep, kill, signal
try:
    from gevent.hub import fork
except ImportError:
    __all__.remove('fork')

from gevent.hub import get_hub

def reinit():
    return get_hub().loop.reinit()
