# Copyright (c) 2015 gevent contributors. See LICENSE for details.
"""gevent friendly implementations of builtin functions."""
from __future__ import absolute_import

import imp
import sys
import gevent.lock

# Normally we'd have the "expected" case inside the try
# (Python 3, because Python 3 is the way forward). But
# under Python 2, the popular `future` library *also* provides
# a `builtins` module---which lacks the __import__ attribute.
# So we test for the old, deprecated version first

try: # Py2
    import __builtin__ as builtins
    _allowed_module_name_types = (basestring,)
    __target__ = '__builtin__'
except ImportError:
    import builtins
    _allowed_module_name_types = (str,)
    __target__ = 'builtins'

_import = builtins.__import__

# We need to protect imports both across threads and across greenlets.
# And the order matters. Note that under 3.4, the global import lock
# and imp module are deprecated. It seems that in all Py3 versions, a
# module lock is used such that this fix is not necessary.
_g_import_lock = gevent.lock.RLock()


def __import__(*args, **kwargs):
    """
    Normally python protects imports against concurrency by doing some locking
    at the C level (at least, it does that in CPython).  This function just
    wraps the normal __import__ functionality in a recursive lock, ensuring that
    we're protected against greenlet import concurrency as well.
    """
    if len(args) > 0 and not issubclass(type(args[0]), _allowed_module_name_types):
        # if a builtin has been acquired as a bound instance method,
        # python knows not to pass 'self' when the method is called.
        # No such protection exists for monkey-patched builtins,
        # however, so this is necessary.
        args = args[1:]
    # TODO: It would be nice not to have to acquire the locks
    # if the module is already imported (in sys.modules), but the interpretation
    # of the arguments is somewhat complex
    imp.acquire_lock()
    try:
        _g_import_lock.acquire()
        try:
            result = _import(*args, **kwargs)
        finally:
            _g_import_lock.release()
    finally:
        imp.release_lock()
    return result

if sys.version_info[:2] >= (3, 3):
    __implements__ = []
else:
    __implements__ = ['__import__']
__all__ = __implements__
