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


from gevent.builtins import __import__ as g_import


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
    'gevent.contextvars': 'contextvars',
}

_PATCH_PREFIX = '__g_patched_module_'

class _SysModulesPatcher(object):

    def __init__(self, importing, extra_all=lambda mod_name: ()):
        self._saved = {}
        self.extra_all = extra_all
        self.importing = importing
        self.green_modules = {
            stdlib_name: importlib.import_module(gevent_name)
            for gevent_name, stdlib_name
            in iteritems(MAPPING)
        }
        self.orig_imported = frozenset(sys.modules)

    def _save(self):
        self.orig_imported = frozenset(sys.modules)

        for modname in self.green_modules:
            self._saved[modname] = sys.modules.get(modname, None)

        self._saved[self.importing] = sys.modules.get(self.importing, None)
        # Anything we've already patched regains its original name during this
        # process; anything imported in the original namespace is temporarily withdrawn.
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
        return self

    module = None

    def __call__(self):
        if self.module is None:
            self.module = self.import_one(self.importing)
        return self

    def import_one(self, module_name):
        patched_name = _PATCH_PREFIX + module_name
        if patched_name in sys.modules:
            return sys.modules[patched_name]

        assert module_name.startswith(self.importing)
        sys.modules.pop(module_name, None)

        module = g_import(module_name, {}, {}, module_name.split('.')[:-1])
        self.module = module
        sys.modules[patched_name] = module
        # On Python 3, we could probably do something much nicer with the
        # import machinery? Set the __loader__ or __finder__ or something like that?
        self._import_all([module])
        return module

    def _import_all(self, queue):
        # Called while monitoring for patch changes.
        while queue:
            module = queue.pop(0)
            for attr_name in tuple(getattr(module, '__all__', ())) + self.extra_all(module.__name__):
                try:
                    getattr(module, attr_name)
                except AttributeError:
                    module_name = module.__name__ + '.' + attr_name
                    sys.modules.pop(module_name, None)
                    new_module = g_import(module_name, {}, {}, attr_name)
                    setattr(module, attr_name, new_module)
                    queue.append(new_module)


def import_patched(module_name, extra_all=lambda mod_name: ()):
    """
    Import *module_name* with gevent monkey-patches active,
    and return an object holding the greened module as *module*.

    Any sub-modules that were imported by the package are also
    saved.

    .. versionchanged:: 1.5a4
       If the module defines ``__all__``, then each of those
       attributes/modules is also imported as part of the same transaction,
       recursively. The order of ``__all__`` is respected. Anything passed in
       *extra_all* (which must be in the same namespace tree) is also imported.

    """

    with cached_platform_architecture():
        # Save the current module state, and restore on exit,
        # capturing desirable changes in the modules package.
        with _SysModulesPatcher(module_name, extra_all) as patcher:
            patcher()
    return patcher


class cached_platform_architecture(object):
    """
    Context manager that caches ``platform.architecture``.

    Some things that load shared libraries (like Cryptodome, via
    dnspython) invoke ``platform.architecture()`` for each one. That
    in turn wants to fork and run commands , which in turn wants to
    call ``threading._after_fork`` if the GIL has been initialized.
    All of that means that certain imports done early may wind up
    wanting to have the hub initialized potentially much earlier than
    before.

    Part of the fix is to observe when that happens and delay
    initializing parts of gevent until as late as possible (e.g., we
    delay importing and creating the resolver until the hub needs it,
    unless explicitly configured).

    The rest of the fix is to avoid the ``_after_fork`` issues by
    first caching the results of platform.architecture before doing
    patched imports.

    (See events.py for similar issues with platform, and
    test__threading_2.py for notes about threading._after_fork if the
    GIL has been initialized)
    """

    _arch_result = None
    _orig_arch = None
    _platform = None

    def __enter__(self):
        import platform
        self._platform = platform
        self._arch_result = platform.architecture()
        self._orig_arch = platform.architecture
        def arch(*args, **kwargs):
            if not args and not kwargs:
                return self._arch_result
            return self._orig_arch(*args, **kwargs)
        platform.architecture = arch
        return self

    def __exit__(self, *_args):
        self._platform.architecture = self._orig_arch
        self._platform = None
