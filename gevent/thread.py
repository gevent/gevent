"""Implementation of the standard :mod:`thread` module that spawns greenlets.

.. note::
    
    This module is a helper for :mod:`gevent.monkey` and is not intended to be
    used directly. For spawning greenlets in your applications, prefer
    :class:`Greenlet` class.
"""

__thread = __import__('thread')
from gevent.hub import getcurrent, GreenletExit
from gevent.greenlet import Greenlet
from gevent.coros import Semaphore as LockType

def get_ident(gr=None):
    if gr is None:
        return id(getcurrent())
    else:
        return id(gr)

def start_new_thread(function, args=(), kwargs={}):
    greenlet = Greenlet.spawn(function, *args, **kwargs)
    return get_ident(greenlet)

def allocate_lock():
    return LockType(1)

def exit():
    raise GreenletExit

if hasattr(__thread, 'stack_size'):
    _original_stack_size = __thread.stack_size
    def stack_size(size=None):
        if size is None:
            return _original_stack_size()
        if size > _original_stack_size():
            return _original_stack_size(size)
        else:
            pass
            # not going to decrease stack_size, because otherwise other greenlets in this thread will suffer

# XXX interrupt_main, _local
