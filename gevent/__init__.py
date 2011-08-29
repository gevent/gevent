# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
"""
gevent is a coroutine-based Python networking library that uses greenlet
to provide a high-level synchronous API on top of libevent event loop.

See http://www.gevent.org/ for the documentation.
"""

version_info = (1, 0, 0, 'dev', None)
__version__ = '1.0dev'
# 'dev' in version_info should be replaced with alpha|beta|candidate|final
# 'dev' in __version__ should be replaced with a|b|rc|<empty string>


__all__ = ['get_hub',
           'Greenlet',
           'GreenletExit',
           'spawn',
           'spawn_later',
           'spawn_raw',
           'joinall',
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
    __import__('socket')  # trigger WSAStartup call
del sys


from gevent.greenlet import Greenlet, joinall, killall
spawn = Greenlet.spawn
spawn_later = Greenlet.spawn_later
from gevent.timeout import Timeout, with_timeout
from gevent.hub import getcurrent, GreenletExit, spawn_raw, sleep, idle, kill, signal
try:
    from gevent.hub import fork
except ImportError:
    __all__.remove('fork')

from gevent.hub import get_hub

def reinit():
    return get_hub().loop.reinit()
