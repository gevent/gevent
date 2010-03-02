# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
"""
gevent is a coroutine-based Python networking library that uses greenlet
to provide a high-level synchronous API on top of libevent event loop.
"""

version_info = (0, 12, 2)
__version__ = '0.12.2'

__all__ = ['Greenlet',
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
           'shutdown',
           'core',
           'reinit']


from gevent.core import reinit
from gevent.greenlet import Greenlet, joinall, killall
spawn = Greenlet.spawn
spawn_later = Greenlet.spawn_later
spawn_link = Greenlet.spawn_link
spawn_link_value = Greenlet.spawn_link_value
spawn_link_exception = Greenlet.spawn_link_exception
from gevent.timeout import Timeout, with_timeout
from gevent.hub import getcurrent, GreenletExit, spawn_raw, sleep, kill, signal, shutdown
try:
    from gevent.hub import fork
except ImportError:
    __all__.remove('fork')
