"""
Cooperative implementation of special cases of :func:`signal.signal`.

This module is designed to work with libev's child watchers, as used by
default in :func:`gevent.os.fork` Note that each SIGCHLD handler will be run
in a new greenlet when the signal is delivered (just like :class:`gevent.hub.signal`)

.. versionadded:: 1.1b4
"""

from __future__ import absolute_import

import signal as _signal

__implements__ = []
__extensions__ = []


_INITIAL = object()

_child_handler = _INITIAL

_signal_signal = _signal.signal
_signal_getsignal = _signal.getsignal


def getsignal(signalnum):
    if signalnum != _signal.SIGCHLD:
        return _signal_getsignal(signalnum)

    global _child_handler
    if _child_handler is _INITIAL:
        _child_handler = _signal_getsignal(_signal.SIGCHLD)

    return _child_handler


def signal(signalnum, handler):
    if signalnum != _signal.SIGCHLD:
        return _signal_signal(signalnum, handler)

    # TODO: raise value error if not called from the main
    # greenlet, just like threads

    if handler != _signal.SIG_IGN and handler != _signal.SIG_DFL and not callable(handler):
        raise TypeError("signal handler must be signal.SIG_IGN, signal.SIG_DFL, or a callable object")

    old_handler = getsignal(signalnum)
    global _child_handler
    _child_handler = handler
    return old_handler


def _on_child_hook():
    # This is called in the hub greenlet. To let the function
    # do more useful work, like use blocking functions,
    # we run it in a new greenlet; see gevent.hub.signal
    if callable(_child_handler):
        # None is a valid value for the frame argument
        from gevent import Greenlet
        greenlet = Greenlet(_child_handler, _signal.SIGCHLD, None)
        greenlet.switch()


import gevent.os

if 'waitpid' in gevent.os.__implements__ and hasattr(_signal, 'SIGCHLD'):
    # Tightly coupled here to gevent.os and its waitpid implementation
    gevent.os._on_child_hook = _on_child_hook
    __implements__.append("signal")
    __implements__.append("getsignal")
else:
    __extensions__.append("signal")
    __extensions__.append("getsignal")

__all__ = __implements__ + __extensions__
