import sys
import os
import imp

version = '%s.%s' % sys.version_info[:2]

missing_modules = {
    'test_smtplib': ['2.4', '2.5'],
    'test_asyncore': ['2.4', '2.5'],
    'test_telnetlib': ['2.4', '2.5'],
    'test_httpservers': ['2.4', '2.5'],
    'test_ftplib': ['2.4', '2.5'],
    'test_wsgiref': ['2.4'],
    'test_socket_ssl': ['2.6', '2.7']}


class ContainsAll(object):
    def __contains__(self, item):
        return True


def patch_all(**kwargs):
    timeout = kwargs.pop('timeout', None)
    kwargs.setdefault('aggressive', True)
    from gevent import monkey
    monkey.patch_all(**kwargs)
    import unittest
    import greentest
    unittest.TestCase = greentest.TestCase0
    if timeout is not None:
        unittest.TestCase.__timeout__ = timeout


def imp_find_dotted_module(name):
    """imp.find_module with dotted names"""
    path = None
    for x in name.split('.'):
        result = imp.find_module(x, path)
        path = [result[1]]
    return result


def prepare_stdlib_test(filename, **kwargs):
    kwargs.setdefault('timeout', 20)
    patch_all(**kwargs)
    import test
    try:
        from test import test_support
    except ImportError:
        sys.stderr.write('test.__file__ = %s\n' % test.__file__)
        raise
    test_support.use_resources = ContainsAll()

    name = os.path.splitext(os.path.basename(filename))[0].replace('_patched', '')

    os.environ['__module_name__'] = name

    try:
        _f, _filename, _ = imp_find_dotted_module('test.%s' % name)
    except:
        if version in missing_modules.get(name, []):
            sys.exit(0)
        sys.stderr.write('Failed to import test.%s\n' % name)
        raise

    module_source = _f.read()
    from patched_tests_setup import disable_tests_in_the_source
    module_source = disable_tests_in_the_source(module_source, name)
    module_code = compile(module_source, _filename, 'exec')

    print >> sys.stderr, 'Testing %s with monkey patching' % _filename
    return module_code
