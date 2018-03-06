# Copyright 2018 gevent. See LICENSE for details.

# Portions of the following are inspired by code from eventlet. I
# believe they are distinct enough that no eventlet copyright would
# apply (they are not a copy or substantial portion of the eventlot
# code).

# Added in gevent 1.3a2. Not public in that release.

from __future__ import absolute_import, print_function

import importlib
import sys

from gevent._compat import PY3
from gevent._compat import iteritems
from gevent._compat import imp_acquire_lock
from gevent._compat import imp_release_lock


from gevent.builtins import __import__ as _import


MAPPING = {
    'gevent.local': '_threading_local',
    'gevent.socket': 'socket',
    'gevent.select': 'select',
    'gevent.ssl': 'ssl',
    'gevent.thread': '_thread' if PY3 else 'thread',
    'gevent.subprocess': 'subprocess',
    'gevent.os': 'os',
    'gevent.threading': 'threading',
    'gevent.builtins': 'builtins' if PY3 else '__builtin__',
    'gevent.signal': 'signal',
    'gevent.time': 'time',
    'gevent.queue': 'queue' if PY3 else 'Queue',
}

_PATCH_PREFIX = '__g_patched_module_'

class _SysModulesPatcher(object):

    def __init__(self, importing):
        self._saved = {}
        self.importing = importing
        self.green_modules = {
            stdlib_name: importlib.import_module(gevent_name)
            for gevent_name, stdlib_name
            in iteritems(MAPPING)
        }
        self.orig_imported = frozenset(sys.modules)

    def _save(self):
        for modname in self.green_modules:
            self._saved[modname] = sys.modules.get(modname, None)

        self._saved[self.importing] = sys.modules.get(self.importing, None)
        # Anything we've already patched regains its original name during this
        # process
        for mod_name, mod in iteritems(sys.modules):
            if mod_name.startswith(_PATCH_PREFIX):
                orig_mod_name = mod_name[len(_PATCH_PREFIX):]
                self._saved[mod_name] = sys.modules.get(orig_mod_name, None)
                self.green_modules[orig_mod_name] = mod

    def _replace(self):
        # Cover the target modules so that when you import the module it
        # sees only the patched versions
        for name, mod in iteritems(self.green_modules):
            sys.modules[name] = mod

    def _restore(self):
        for modname, mod in iteritems(self._saved):
            if mod is not None:
                sys.modules[modname] = mod
            else:
                try:
                    del sys.modules[modname]
                except KeyError:
                    pass
        # Anything from the same package tree we imported this time
        # needs to be saved so we can restore it later, and so it doesn't
        # leak into the namespace.
        pkg_prefix = self.importing.split('.', 1)[0]
        for modname, mod in list(iteritems(sys.modules)):
            if (modname not in self.orig_imported
                    and modname != self.importing
                    and not modname.startswith(_PATCH_PREFIX)
                    and modname.startswith(pkg_prefix)):
                sys.modules[_PATCH_PREFIX + modname] = mod
                del sys.modules[modname]

    def __exit__(self, t, v, tb):
        try:
            self._restore()
        finally:
            imp_release_lock()

    def __enter__(self):
        imp_acquire_lock()
        self._save()
        self._replace()


def import_patched(module_name):
    """
    Import *module_name* with gevent monkey-patches active,
    and return the greened module.

    Any sub-modules that were imported by the package are also
    saved.

    """
    patched_name = _PATCH_PREFIX + module_name
    if patched_name in sys.modules:
        return sys.modules[patched_name]


    # Save the current module state, and restore on exit,
    # capturing desirable changes in the modules package.
    with _SysModulesPatcher(module_name):
        sys.modules.pop(module_name, None)

        module = _import(module_name, {}, {}, module_name.split('.')[:-1])
        sys.modules[patched_name] = module

    return module
