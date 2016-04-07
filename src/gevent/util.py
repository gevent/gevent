# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.
"""
Low-level utilities.
"""

from __future__ import absolute_import

import functools

__all__ = ['wrap_errors']


class wrap_errors(object):
    """
    Helper to make function return an exception, rather than raise it.

    Because every exception that is unhandled by greenlet will be logged,
    it is desirable to prevent non-error exceptions from leaving a greenlet.
    This can done with a simple ``try/except`` construct::

        def wrapped_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (TypeError, ValueError, AttributeError) as ex:
                return ex

    This class provides a shortcut to write that in one line::

        wrapped_func = wrap_errors((TypeError, ValueError, AttributeError), func)

    It also preserves ``__str__`` and ``__repr__`` of the original function.
    """
    # QQQ could also support using wrap_errors as a decorator

    def __init__(self, errors, func):
        """
        Calling this makes a new function from *func*, such that it catches *errors* (an
        :exc:`BaseException` subclass, or a tuple of :exc:`BaseException` subclasses) and
        return it as a value.
        """
        self.__errors = errors
        self.__func = func
        # Set __doc__, __wrapped__, etc, especially useful on Python 3.
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        func = self.__func
        try:
            return func(*args, **kwargs)
        except self.__errors as ex:
            return ex

    def __str__(self):
        return str(self.__func)

    def __repr__(self):
        return repr(self.__func)

    def __getattr__(self, name):
        return getattr(self.__func, name)
