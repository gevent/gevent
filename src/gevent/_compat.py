# -*- coding: utf-8 -*-
"""
internal gevent python 2/python 3 bridges. Not for external use.
"""

from __future__ import print_function, absolute_import, division

import sys


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3
PYPY = hasattr(sys, 'pypy_version_info')
WIN = sys.platform.startswith("win")

## Types

if PY3:
    string_types = (str,)
    integer_types = (int,)
    text_type = str
    native_path_types = (str, bytes)

else:
    import __builtin__ # pylint:disable=import-error
    string_types = (__builtin__.basestring,)
    text_type = __builtin__.unicode
    integer_types = (int, __builtin__.long)
    native_path_types = string_types


## Exceptions
if PY3:
    def reraise(t, value, tb=None): # pylint:disable=unused-argument
        if value.__traceback__ is not tb and tb is not None:
            raise value.with_traceback(tb)
        raise value

else:
    from gevent._util_py2 import reraise # pylint:disable=import-error,no-name-in-module
    reraise = reraise # export

## Functions
if PY3:
    iteritems = dict.items
    itervalues = dict.values
    xrange = range
else:
    iteritems = dict.iteritems # python 3: pylint:disable=no-member
    itervalues = dict.itervalues # python 3: pylint:disable=no-member
    xrange = __builtin__.xrange

# fspath from 3.6 os.py, but modified to raise the same exceptions as the
# real native implementation.
# Define for testing
def _fspath(path):
    """
    Return the path representation of a path-like object.

    If str or bytes is passed in, it is returned unchanged. Otherwise the
    os.PathLike interface is used to get the path representation. If the
    path representation is not str or bytes, TypeError is raised. If the
    provided path is not str, bytes, or os.PathLike, TypeError is raised.
    """
    if isinstance(path, native_path_types):
        return path

    # Work from the object's type to match method resolution of other magic
    # methods.
    path_type = type(path)
    try:
        path_type_fspath = path_type.__fspath__
    except AttributeError:
        raise TypeError("expected str, bytes or os.PathLike object, "
                        "not " + path_type.__name__)

    path_repr = path_type_fspath(path)
    if isinstance(path_repr, native_path_types):
        return path_repr

    raise TypeError("expected {}.__fspath__() to return str or bytes, "
                    "not {}".format(path_type.__name__,
                                    type(path_repr).__name__))
try:
    from os import fspath # pylint: disable=unused-import,no-name-in-module
except ImportError:
    # if not available, use the Python version as transparently as
    # possible
    fspath = _fspath
    fspath.__name__ = 'fspath'
