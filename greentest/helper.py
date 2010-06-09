import sys
import os

version = '%s.%s' % sys.version_info[:2]

missing_modules = {
    'test_smtplib': ['2.4', '2.5'],
    'test_asyncore': ['2.4', '2.5'],
    'test_telnetlib': ['2.4', '2.5'],
    'test_httpservers': ['2.4', '2.5'],
    'test_ftplib': ['2.4', '2.5'],
    'test_wsgiref': ['2.4'],
    'test_socket_ssl': ['2.6', '2.7']
}


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
        if version in missing_modules.get(name, []): 
            sys.exit(0)
        raise

    module = getattr(package, name)
    _filename = module.__file__.replace('.pyc', '.py')

    module_source = open(_filename).read()
    from patched_tests_setup import disable_tests_in_the_source
    module_source = disable_tests_in_the_source(module_source, name)
    module_code = compile(module_source, _filename, 'exec')

    print >> sys.stderr, 'Testing %s with monkey patching' % _filename
    return module_code
