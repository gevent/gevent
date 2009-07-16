version_info = (0, 9, 1)
__version__ = '0.9.1'

__all__ = ['getcurrent',
           'TimeoutError',
           'Timeout',
           'spawn',
           'spawn_later',
           'kill',
           'sleep',
           'signal',
           'with_timeout',
           'fork',
           'reinit']

# add here Queue, Event, Pipe?, Socket?

from gevent.greenlet import *
from gevent import core
reinit = core.reinit


def timeout(*args, **kwargs):
    import warnings
    warnings.warn("timeout is deprecated; use Timeout", DeprecationWarning, stacklevel=2)
    return Timeout(*args, **kwargs)
