import sys
import os
import re
import doctest
import unittest
import traceback
import gevent
from gevent import socket
from greentest import walk_modules

# Ignore tracebacks: ZeroDivisionError


def myfunction(*args, **kwargs):
    pass


if __name__ == '__main__':
    cwd = os.getcwd()
    try:
        allowed_modules = sys.argv[1:]
        sys.path.append('.')
        base = os.path.dirname(gevent.__file__)
        print (base)
        os.chdir('..')

        globs = {'myfunction': myfunction, 'gevent': gevent, 'socket': socket}

        modules = set()

        def add_module(name, path):
            if allowed_modules and name not in allowed_modules:
                return
            modules.add((name, path))

        for path, module in walk_modules():
            add_module(module, path)
        add_module('setup', 'setup.py')

        if not modules:
            sys.exit('No modules found matching %s' % ' '.join(allowed_modules))

        suite = unittest.TestSuite()
        tests_count = 0
        modules_count = 0
        for m, path in modules:
            if re.search('^\s*>>> ', open(path).read(), re.M):
                try:
                    s = doctest.DocTestSuite(m, extraglobs=globs)
                    print ('%s (from %s): %s tests' % (m, path, len(s._tests)))
                    suite.addTest(s)
                    modules_count += 1
                    tests_count += len(s._tests)
                except Exception:
                    traceback.print_exc()
                    sys.stderr.write('Failed to process %s\n\n' % path)
        print ('Total: %s tests in %s modules' % (tests_count, modules_count))
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    finally:
        os.chdir(cwd)
