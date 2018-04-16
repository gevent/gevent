# -*- coding: utf-8 -*-
"""
internal gevent utilities, not for external use.
"""

from __future__ import print_function, absolute_import, division

from functools import update_wrapper

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
    Copy attributes defined in ``source.__dict__`` to the dictionary
    in globs (which should be the caller's :func:`globals`).

    Names that start with ``__`` are ignored (unless they are in
    *dunder_names_to_keep*). Anything found in *names_to_ignore* is
    also ignored.

    If *only_names* is given, only those attributes will be
    considered. In this case, *ignore_missing_names* says whether or
    not to raise an :exc:`AttributeError` if one of those names can't
    be found.

    If *cleanup_globs* has a true value, then common things imported but
    not used at runtime are removed, including this function.

    Returns a list of the names copied; this should be assigned to ``__imports__``.
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

def import_c_accel(globs, cname):
    """
    Import the C-accelerator for the __name__
    and copy its globals.
    """

    name = globs.get('__name__')

    if not name or name == cname:
        # Do nothing if we're being exec'd as a file (no name)
        # or we're running from the C extension
        return


    from gevent._compat import PURE_PYTHON
    if PURE_PYTHON:
        return

    import importlib
    import warnings
    with warnings.catch_warnings():
        # Python 3.7 likes to produce
        # "ImportWarning: can't resolve
        #   package from __spec__ or __package__, falling back on
        #   __name__ and __path__"
        # when we load cython compiled files. This is probably a bug in
        # Cython, but it doesn't seem to have any consequences, it's
        # just annoying to see and can mess up our unittests.
        warnings.simplefilter('ignore', ImportWarning)
        mod = importlib.import_module(cname)

    # By adopting the entire __dict__, we get a more accurate
    # __file__ and module repr, plus we don't leak any imported
    # things we no longer need.
    globs.clear()
    globs.update(mod.__dict__)

    if 'import_c_accel' in globs:
        del globs['import_c_accel']


class Lazy(object):
    """
    A non-data descriptor used just like @property. The
    difference is the function value is assigned to the instance
    dict the first time it is accessed and then the function is never
    called agoin.
    """
    def __init__(self, func):
        self.data = (func, func.__name__)
        update_wrapper(self, func)

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
        update_wrapper(self, func)

    def __get__(self, inst, class_):
        if inst is None:
            return self

        return self.func(inst)

def gmctime():
    """
    Returns the current time as a string in RFC3339 format.
    """
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

try:
    from zope.interface import Interface
    from zope.interface import implementer
    from zope.interface import Attribute
except ImportError:
    class Interface(object):
        pass
    def implementer(_iface):
        def dec(c):
            return c
        return dec

    def Attribute(s):
        return s

Interface = Interface
implementer = implementer
Attribute = Attribute
