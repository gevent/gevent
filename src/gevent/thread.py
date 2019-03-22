"""
Implementation of the standard :mod:`thread` module that spawns greenlets.

.. note::

    This module is a helper for :mod:`gevent.monkey` and is not
    intended to be used directly. For spawning greenlets in your
    applications, prefer higher level constructs like
    :class:`gevent.Greenlet` class or :func:`gevent.spawn`.
"""
from __future__ import absolute_import
import sys

__implements__ = [
    'allocate_lock',
    'get_ident',
    'exit',
    'LockType',
    'stack_size',
    'start_new_thread',
    '_local',
]

__imports__ = ['error']
if sys.version_info[0] == 2:
    import thread as __thread__ # pylint:disable=import-error
    PY2 = True
    PY3 = False
    # Name the `future` backport that might already have been imported;
    # Importing `pkg_resources` imports this, for example.
    __alternate_targets__ = ('_thread',)
else:
    import _thread as __thread__ # pylint:disable=import-error
    PY2 = False
    PY3 = True
    __target__ = '_thread'
    __imports__ += [
        'TIMEOUT_MAX',
        'allocate',
        'exit_thread',
        'interrupt_main',
        'start_new'
    ]


error = __thread__.error

from gevent._compat import PYPY
from gevent._util import copy_globals
from gevent.hub import getcurrent, GreenletExit
from gevent.greenlet import Greenlet
from gevent.lock import BoundedSemaphore
from gevent.local import local as _local

if hasattr(__thread__, 'RLock'):
    assert PY3 or PYPY
    # Added in Python 3.4, backported to PyPy 2.7-7.0
    __imports__.append("RLock")



def get_ident(gr=None):
    if gr is None:
        gr = getcurrent()
    return id(gr)


def start_new_thread(function, args=(), kwargs=None):
    if kwargs is not None:
        greenlet = Greenlet.spawn(function, *args, **kwargs)
    else:
        greenlet = Greenlet.spawn(function, *args)
    return get_ident(greenlet)


class LockType(BoundedSemaphore):
    # Change the ValueError into the appropriate thread error
    # and any other API changes we need to make to match behaviour
    _OVER_RELEASE_ERROR = __thread__.error

    if PYPY and PY3:
        _OVER_RELEASE_ERROR = RuntimeError

    if PY3:
        _TIMEOUT_MAX = __thread__.TIMEOUT_MAX # python 2: pylint:disable=no-member

        def acquire(self, blocking=True, timeout=-1):
            # Transform the default -1 argument into the None that our
            # semaphore implementation expects, and raise the same error
            # the stdlib implementation does.
            if timeout == -1:
                timeout = None
            if not blocking and timeout is not None:
                raise ValueError("can't specify a timeout for a non-blocking call")
            if timeout is not None:
                if timeout < 0:
                    # in C: if(timeout < 0 && timeout != -1)
                    raise ValueError("timeout value must be strictly positive")
                if timeout > self._TIMEOUT_MAX:
                    raise OverflowError('timeout value is too large')

            return BoundedSemaphore.acquire(self, blocking, timeout)

allocate_lock = LockType


def exit():
    raise GreenletExit


if hasattr(__thread__, 'stack_size'):
    _original_stack_size = __thread__.stack_size

    def stack_size(size=None):
        if size is None:
            return _original_stack_size()
        if size > _original_stack_size():
            return _original_stack_size(size)
        # not going to decrease stack_size, because otherwise other
        # greenlets in this thread will suffer
else:
    __implements__.remove('stack_size')

__imports__ = copy_globals(__thread__, globals(),
                           only_names=__imports__,
                           ignore_missing_names=True)

__all__ = __implements__ + __imports__
__all__.remove('_local')


# XXX interrupt_main
# XXX _count()
