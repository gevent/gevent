import os
import re
import doctest
import unittest
import gevent

base = os.path.dirname(gevent.__file__)
modules = set()

def myfunction(*args, **kwargs):
    pass

globs = {'myfunction': myfunction, 'gevent': gevent}

for path, dirs, files in os.walk(base):
    package = 'gevent' + path.replace(base, '').replace('/', '.')
    modules.add((package, os.path.join(path, '__init__.py')))
    for f in files:
        module = None
        if f.endswith('.py'):
            module = f[:-3]
        if module:
            modules.add((package + '.' + module, os.path.join(path, f)))

suite = unittest.TestSuite()
tests_count = 0
modules_count = 0
for m, path in modules:
    if re.search('^\s*>>> ', open(path).read(), re.M):
        s = doctest.DocTestSuite(m, extraglobs=globs)
        print '%s (from %s): %s tests' % (m, path, len(s._tests))
        suite.addTest(s)
        modules_count += 1
        tests_count += len(s._tests)
print 'Total: %s tests in %s modules' % (tests_count, modules_count)
runner = unittest.TextTestRunner(verbosity=2)
runner.run(suite)
