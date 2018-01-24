from __future__ import print_function
import doctest
import functools
import os
import re
import sys
import traceback
import unittest

import gevent
from gevent import socket
from greentest import walk_modules
from greentest import sysinfo

# Ignore tracebacks: ZeroDivisionError


def myfunction(*args, **kwargs):
    pass


class RENormalizingOutputChecker(doctest.OutputChecker):
    """
    Pattern-normalizing output checker. Inspired by one used in zope.testing.
    """

    def __init__(self, patterns):
        self.transformers = [functools.partial(re.sub, replacement) for re, replacement in patterns]

    def check_output(self, want, got, optionflags):
        if got == want:
            return True

        for transformer in self.transformers:
            want = transformer(want)
            got = transformer(got)

        return doctest.OutputChecker.check_output(self, want, got, optionflags)

FORBIDDEN_MODULES = set()
if sysinfo.WIN:
    FORBIDDEN_MODULES |= {
        # Uses commands only found on posix
        'gevent.subprocess',
    }

if __name__ == '__main__':
    cwd = os.getcwd()
    try:
        allowed_modules = sys.argv[1:]
        sys.path.append('.')
        base = os.path.dirname(gevent.__file__)
        print(base)
        os.chdir('../..')

        globs = {'myfunction': myfunction, 'gevent': gevent, 'socket': socket}

        modules = set()

        def add_module(name, path):
            if allowed_modules and name not in allowed_modules:
                return
            if name in FORBIDDEN_MODULES:
                return
            modules.add((name, path))

        for path, module in walk_modules():
            add_module(module, path)
        add_module('setup', 'setup.py')

        if not modules:
            sys.exit('No modules found matching %s' % ' '.join(allowed_modules))

        suite = unittest.TestSuite()
        checker = RENormalizingOutputChecker((
            # Normalize subprocess.py: BSD ls is in the example, gnu ls outputs
            # 'cannot access'
            (re.compile('cannot access non_existent_file: No such file or directory'),
             'non_existent_file: No such file or directory'),
            # Python 3 bytes add a "b".
            (re.compile(r'b(".*?")'), r"\1"),
            (re.compile(r"b('.*?')"), r"\1"),
        ))

        tests_count = 0
        modules_count = 0
        for m, path in sorted(modules):
            with open(path, 'rb') as f:
                contents = f.read()
            if re.search(br'^\s*>>> ', contents, re.M):
                try:
                    s = doctest.DocTestSuite(m, extraglobs=globs, checker=checker)
                    test_count = len(s._tests) # pylint: disable=W0212
                    print('%s (from %s): %s tests' % (m, path, test_count))
                    suite.addTest(s)
                    modules_count += 1
                    tests_count += test_count
                except Exception:
                    traceback.print_exc()
                    sys.stderr.write('Failed to process %s\n\n' % path)
        print('Total: %s tests in %s modules' % (tests_count, modules_count))
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    finally:
        os.chdir(cwd)
