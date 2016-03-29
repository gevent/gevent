# -*- coding: utf-8 -*-
"""
internal gevent utilities, not for external use.
"""

from __future__ import print_function, absolute_import, division

from gevent._compat import iteritems


class _NONE(object):
    """
    A special object you must never pass to any gevent API.
    Used as a marker object for keyword arguments that cannot have the
    builtin None (because that might be a valid value).
    """
    __slots__ = ()

    def __repr__(self):
        return '<default value>'

_NONE = _NONE()

def copy_globals(source,
                 globs,
                 only_names=None,
                 ignore_missing_names=False,
                 names_to_ignore=(),
                 dunder_names_to_keep=('__implements__', '__all__', '__imports__'),
                 cleanup_globs=True):
    """
    Copy attributes defined in `source.__dict__` to the dictionary in globs
    (which should be the caller's globals()).

    Names that start with `__` are ignored (unless they are in
    *dunder_names_to_keep*). Anything found in *names_to_ignore* is
    also ignored.

    If *only_names* is given, only those attributes will be considered.
    In this case, *ignore_missing_names* says whether or not to raise an AttributeError
    if one of those names can't be found.

    If cleanup_globs has a true value, then common things imported but not used
    at runtime are removed, including this function.

    Returns a list of the names copied
    """
    if only_names:
        if ignore_missing_names:
            items = ((k, getattr(source, k, _NONE)) for k in only_names)
        else:
            items = ((k, getattr(source, k)) for k in only_names)
    else:
        items = iteritems(source.__dict__)

    copied = []
    for key, value in items:
        if value is _NONE:
            continue
        if key in names_to_ignore:
            continue
        if key.startswith("__") and key not in dunder_names_to_keep:
            continue
        globs[key] = value
        copied.append(key)

    if cleanup_globs:
        if 'copy_globals' in globs:
            del globs['copy_globals']

    return copied

class Lazy(object):
    """
    A non-data descriptor used just like @property. The
    difference is the function value is assigned to the instance
    dict the first time it is accessed and then the function is never
    called agoin.
    """
    def __init__(self, func):
        self.data = (func, func.__name__)

    def __get__(self, inst, class_):
        if inst is None:
            return self

        func, name = self.data
        value = func(inst)
        inst.__dict__[name] = value
        return value

class readproperty(object):
    """
    A non-data descriptor like @property. The difference is that
    when the property is assigned to, it is cached in the instance
    and the function is not called on that instance again.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, inst, class_):
        if inst is None:
            return self

        return self.func(inst)
