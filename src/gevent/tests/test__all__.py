# Check __all__, __implements__, __extensions__, __imports__ of the modules

from __future__ import print_function

import sys
import unittest
import types
import importlib
import warnings

from gevent.testing import six
from gevent.testing import modules
from gevent.testing.sysinfo import PLATFORM_SPECIFIC_SUFFIXES
from gevent.testing.util import debug

from gevent._patcher import MAPPING

class ANY(object):
    def __contains__(self, item):
        return True

ANY = ANY()

NOT_IMPLEMENTED = {
    'socket': ['CAPI'],
    'thread': ['allocate', 'exit_thread', 'interrupt_main', 'start_new'],
    'select': ANY,
    'os': ANY,
    'threading': ANY,
    'builtins' if six.PY3 else '__builtin__': ANY,
    'signal': ANY,
}

COULD_BE_MISSING = {
    'socket': ['create_connection', 'RAND_add', 'RAND_egd', 'RAND_status'],
    'subprocess': ['_posixsubprocess'],
}

# Things without an __all__ should generally be internal implementation
# helpers
NO_ALL = {
    'gevent.threading',
    'gevent._util',
    'gevent._compat',
    'gevent._socketcommon',
    'gevent._fileobjectcommon',
    'gevent._fileobjectposix',
    'gevent._tblib',
    'gevent._corecffi',
    'gevent._patcher',
    'gevent._ffi',
}

ALLOW_IMPLEMENTS = [
    'gevent._queue',
]

# A list of modules that may contain things that aren't actually, technically,
# extensions, but that need to be in __extensions__ anyway due to the way,
# for example, monkey patching, needs to work.
EXTRA_EXTENSIONS = []
if sys.platform.startswith('win'):
    EXTRA_EXTENSIONS.append('gevent.signal')



_MISSING = '<marker object>'

def _create_tests(cls):
    path = modname = orig_modname = None

    for path, modname in modules.walk_modules(include_so=False, recursive=True, check_optional=False):
        orig_modname = modname
        test_name = 'test_%s' % orig_modname.replace('.', '_')

        modname = modname.replace('gevent.', '').split('.')[0]

        fn = lambda self, n=orig_modname: self._test(n)

        if not modname: # pragma: no cover
            # With walk_modules, can we even get here?
            fn = unittest.skip(
                "No such module '%s' at '%s'" % (orig_modname, path))(fn)

        setattr(cls, test_name, fn)

    return cls

@_create_tests
class Test(unittest.TestCase):

    stdlib_has_all = False
    stdlib_all = ()
    stdlib_name = None
    stdlib_module = None
    module = None
    modname = None
    __implements__ = __extensions__ = __imports__ = ()

    def check_all(self):
        # Check that __all__ is present and does not contain invalid entries
        if not hasattr(self.module, '__all__'):
            self.assertIn(self.modname, NO_ALL)
            return
        names = {}
        six.exec_("from %s import *" % self.modname, names)
        names.pop('__builtins__', None)
        self.assertEqual(sorted(names), sorted(self.module.__all__))

    def check_all_formula(self):
        # Check __all__ = __implements__ + __extensions__ + __imported__
        all_calculated = self.__implements__ + self.__imports__ + self.__extensions__
        self.assertEqual(sorted(all_calculated), sorted(self.module.__all__))

    def check_implements_presence_justified(self):
        # Check that __implements__ is present only if the module is modeled
        # after a module from stdlib (like gevent.socket).

        if self.modname in ALLOW_IMPLEMENTS:
            return
        if self.__implements__ is not None and self.stdlib_module is None:
            raise AssertionError('%r has __implements__ but no stdlib counterpart (%s)'
                                 % (self.modname, self.stdlib_name))

    def set_stdlib_all(self):
        self.assertIsNotNone(self.stdlib_module)
        self.stdlib_has_all = True
        self.stdlib_all = getattr(self.stdlib_module, '__all__', None)
        if self.stdlib_all is None:
            self.stdlib_has_all = False
            self.stdlib_all = dir(self.stdlib_module)
            self.stdlib_all = [name for name in self.stdlib_all if not name.startswith('_')]
            self.stdlib_all = [name for name in self.stdlib_all if not isinstance(getattr(self.stdlib_module, name), types.ModuleType)]

    def check_implements_subset_of_stdlib_all(self):
        # Check that __implements__ + __imports__ is a subset of the
        # corresponding standard module __all__ or dir()
        for name in self.__implements__ + self.__imports__:
            if name in self.stdlib_all:
                continue
            if name in COULD_BE_MISSING.get(self.stdlib_name, ()):
                continue
            if name in dir(self.stdlib_module):  # like thread._local which is not in thread.__all__
                continue
            raise AssertionError('%r is not found in %r.__all__ nor in dir(%r)' % (name, self.stdlib_module, self.stdlib_module))

    def check_implements_actually_implements(self):
        # Check that the module actually implements the entries from
        # __implements__

        for name in self.__implements__:
            item = getattr(self.module, name)
            try:
                stdlib_item = getattr(self.stdlib_module, name)
                self.assertIsNot(item, stdlib_item)
            except AttributeError:
                if name not in COULD_BE_MISSING.get(self.stdlib_name, []):
                    raise

    def check_imports_actually_imports(self):
        # Check that the module actually imports the entries from
        # __imports__
        for name in self.__imports__:
            item = getattr(self.module, name)
            stdlib_item = getattr(self.stdlib_module, name)
            self.assertIs(item, stdlib_item)

    def check_extensions_actually_extend(self):
        # Check that the module actually defines new entries in
        # __extensions__

        if self.modname in EXTRA_EXTENSIONS:
            return
        for name in self.__extensions__:
            if hasattr(self.stdlib_module, name):
                raise AssertionError("'%r' is not an extension, it is found in %r" % (name, self.stdlib_module))

    def check_completeness(self): # pylint:disable=too-many-branches
        # Check that __all__ (or dir()) of the corresponsing stdlib is
        # a subset of __all__ of this module

        missed = []
        for name in self.stdlib_all:
            if name not in getattr(self.module, '__all__', []):
                missed.append(name)

        # handle stuff like ssl.socket and ssl.socket_error which have no reason to be in gevent.ssl.__all__
        if not self.stdlib_has_all:
            for name in missed[:]:
                if hasattr(self.module, name):
                    missed.remove(name)

        # remove known misses
        not_implemented = NOT_IMPLEMENTED.get(self.stdlib_name)
        if not_implemented is not None:
            result = []
            for name in missed:
                if name in not_implemented:
                    # We often don't want __all__ to be set because we wind up
                    # documenting things that we just copy in from the stdlib.
                    # But if we implement it, don't print a warning
                    if getattr(self.module, name, _MISSING) is _MISSING:
                        debug('IncompleteImplWarning: %s.%s' % (self.modname, name))
                else:
                    result.append(name)
            missed = result

        if missed:
            if self.stdlib_has_all:
                msg = '''The following items
              in %r.__all__
are missing from %r:
                 %r''' % (self.stdlib_module, self.module, missed)
            else:
                msg = '''The following items
          in dir(%r)
are missing from %r:
                 %r''' % (self.stdlib_module, self.module, missed)
            raise AssertionError(msg)

    def _test(self, modname):
        if modname.endswith(PLATFORM_SPECIFIC_SUFFIXES):
            return

        self.modname = modname
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            try:
                self.module = importlib.import_module(modname)
            except ImportError:
                if modname in modules.OPTIONAL_MODULES:
                    raise unittest.SkipTest("Unable to import %s" % modname)
                raise

        self.check_all()

        self.__implements__ = getattr(self.module, '__implements__', None)
        self.__imports__ = getattr(self.module, '__imports__', [])
        self.__extensions__ = getattr(self.module, '__extensions__', [])

        self.stdlib_name = MAPPING.get(modname)
        self.stdlib_module = None

        if self.stdlib_name is not None:
            try:
                self.stdlib_module = __import__(self.stdlib_name)
            except ImportError:
                pass

        self.check_implements_presence_justified()

        if self.stdlib_module is None:
            return

        # use __all__ as __implements__
        if self.__implements__ is None:
            self.__implements__ = sorted(self.module.__all__)

        self.set_stdlib_all()
        self.check_implements_subset_of_stdlib_all()
        self.check_implements_actually_implements()
        self.check_imports_actually_imports()
        self.check_extensions_actually_extend()
        self.check_completeness()




if __name__ == "__main__":
    unittest.main()
