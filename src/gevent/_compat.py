# -*- coding: utf-8 -*-
"""
internal gevent python 2/python 3 bridges. Not for external use.
"""

from __future__ import print_function, absolute_import, division

import sys
import os


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3
PYPY = hasattr(sys, 'pypy_version_info')
WIN = sys.platform.startswith("win")
LINUX = sys.platform.startswith('linux')
OSX = sys.platform == 'darwin'


PURE_PYTHON = PYPY or os.getenv('PURE_PYTHON')

## Types

if PY3:
    string_types = (str,)
    integer_types = (int,)
    text_type = str
    native_path_types = (str, bytes)
    thread_mod_name = '_thread'

else:
    import __builtin__ # pylint:disable=import-error
    string_types = (__builtin__.basestring,)
    text_type = __builtin__.unicode
    integer_types = (int, __builtin__.long)
    native_path_types = string_types
    thread_mod_name = 'thread'

def NativeStrIO():
    import io
    return io.BytesIO() if str is bytes else io.StringIO()

## Exceptions
if PY3:
    def reraise(t, value, tb=None): # pylint:disable=unused-argument
        if value.__traceback__ is not tb and tb is not None:
            raise value.with_traceback(tb)
        raise value
    def exc_clear():
        pass

else:
    from gevent._util_py2 import reraise # pylint:disable=import-error,no-name-in-module
    reraise = reraise # export
    exc_clear = sys.exc_clear

## import locks
try:
    # In Python 3.4 and newer in CPython and PyPy3,
    # imp.acquire_lock and imp.release_lock are delegated to
    # '_imp'. (Which is also used by importlib.) 'imp' itself is
    # deprecated. Avoid that warning.
    import _imp as imp
except ImportError:
    import imp
imp_acquire_lock = imp.acquire_lock
imp_release_lock = imp.release_lock

## Functions
if PY3:
    iteritems = dict.items
    itervalues = dict.values
    xrange = range
    izip = zip

else:
    iteritems = dict.iteritems # python 3: pylint:disable=no-member
    itervalues = dict.itervalues # python 3: pylint:disable=no-member
    xrange = __builtin__.xrange
    from itertools import izip # python 3: pylint:disable=no-member,no-name-in-module
    izip = izip

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

try:
    from os import fsencode # pylint: disable=unused-import,no-name-in-module
except ImportError:
    encoding = sys.getfilesystemencoding() or ('utf-8' if not WIN else 'mbcs')
    errors = 'strict' if WIN and encoding == 'mbcs' else 'surrogateescape'

    # Added in 3.2, so this is for Python 2.7. Note that it doesn't have
    # sys.getfilesystemencodeerrors(), which was added in 3.6
    def fsencode(filename):
        """Encode filename (an os.PathLike, bytes, or str) to the filesystem
        encoding with 'surrogateescape' error handler, return bytes unchanged.
        On Windows, use 'strict' error handler if the file system encoding is
        'mbcs' (which is the default encoding).
        """
        filename = fspath(filename)  # Does type-checking of `filename`.
        if isinstance(filename, bytes):
            return filename

        try:
            return filename.encode(encoding, errors)
        except LookupError:
            # Can't encode it, and the error handler doesn't
            # exist. Probably on Python 2 with an astral character.
            # Not sure how to handle this.
            raise UnicodeEncodeError("Can't encode path to filesystem encoding")


## Clocks
try:
    # Python 3.3+ (PEP 418)
    from time import perf_counter
    perf_counter = perf_counter
except ImportError:
    import time

    if sys.platform == "win32":
        perf_counter = time.clock
    else:
        perf_counter = time.time
