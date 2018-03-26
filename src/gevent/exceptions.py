# -*- coding: utf-8 -*-
# copyright 2018 gevent
"""
Exceptions.

.. versionadded:: 1.3b1

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


__all__ = [
    'LoopExit',
]


class LoopExit(Exception):
    """
    Exception thrown when the hub finishes running.

    In a normal application, this is never thrown or caught
    explicitly. The internal implementation of functions like
    :func:`join` and :func:`joinall` may catch it, but user code
    generally should not.

    .. caution::
       Errors in application programming can also lead to this exception being
       raised. Some examples include (but are not limited too):

       - greenlets deadlocking on a lock;
       - using a socket or other gevent object with native thread
         affinity from a different thread

    """


class BlockingSwitchOutError(AssertionError):
    pass


class InvalidSwitchError(AssertionError):
    pass


class ConcurrentObjectUseError(AssertionError):
    # raised when an object is used (waited on) by two greenlets
    # independently, meaning the object was entered into a blocking
    # state by one greenlet and then another while still blocking in the
    # first one
    pass
