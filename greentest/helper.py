import sys
import os

class ContainsAll(object):
    def __contains__(self, item):
        return True

def patch_all(timeout=None):
    from gevent import monkey
    monkey.patch_all(aggressive=True)
    import unittest, greentest
    unittest.TestCase = greentest.TestCase
    if timeout is not None:
        unittest.TestCase.__timeout__ = timeout


def prepare_stdlib_test(filename):
    patch_all(timeout=20)
    from test import test_support
    test_support.use_resources = ContainsAll()

    name = filename.replace('_patched', '').replace('.py', '')

    os.environ['__module_name__'] = name

    try:
        # XXX importing just to find where it resides; need a function that just returns the path
        package = __import__('test.%s' % name)
    except:
        print >> sys.stderr, 'ModuleNotFoundWarning: cannot import test.%s' % name
        sys.exit(0)

    module = getattr(package, name)
    _filename = module.__file__.replace('.pyc', '.py')

    module_source = open(_filename).read()
    from patched_tests_setup import disable_tests_in_the_source
    module_source = disable_tests_in_the_source(module_source, name)
    module_code = compile(module_source, _filename, 'exec')

    print >> sys.stderr, 'Testing %s with monkey patching' % _filename
    return module_code
