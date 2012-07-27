import sys
import os
import imp
import tempfile
import glob
from pipes import quote

chdir = os.path.join(tempfile.gettempdir(), 'gevent-test')
try:
    os.makedirs(chdir)
except EnvironmentError:
    pass

version = '%s.%s' % sys.version_info[:2]

missing_modules = {
    'test_smtplib': ['2.4', '2.5'],
    'test_asyncore': ['2.4', '2.5'],
    'test_telnetlib': ['2.4', '2.5'],
    'test_httpservers': ['2.4', '2.5'],
    'test_ftplib': ['2.4', '2.5'],
    'test_wsgiref': ['2.4'],
    'test_socket_ssl': ['2.6', '2.7', '3.1', '3.2'],
    'test_patched_urllib2_localnet.py': ['3.1', '3.2'],
    'test_ssl': ['2.5'],
}


class ContainsAll(object):
    def __contains__(self, item):
        return True


def patch_all(timeout=None):
    import greentest
    from gevent import monkey
    monkey.patch_all(aggressive=True)
    import unittest
    unittest.TestCase = greentest.TestCase
    unittest.TestCase.check_totalrefcount = False
    unittest.TestCase.error_fatal = False
    if timeout is not None:
        unittest.TestCase.__timeout__ = timeout


def imp_find_dotted_module(name):
    """imp.find_module with dotted names"""
    path = None
    for x in name.split('.'):
        result = imp.find_module(x, path)
        path = [result[1]]
    return result


def prepare_stdlib_test(filename, assets=None):
    patch_all(timeout=20)
    import test
    try:
        if sys.version_info[0] >= 3:
            from test import support as test_support
        else:
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
    from patched_tests_setup import disable_tests_in_source
    module_source = disable_tests_in_source(module_source, name)
    module_code = compile(module_source, _filename, 'exec')

    print >> sys.stderr, 'Testing %s with monkey patching' % _filename

    copy_assets(os.path.dirname(_filename), assets)
    os.chdir(chdir)
    return module_code


def copy_assets(directory, assets):
    if assets:
        cwd = os.getcwd()
        os.chdir(directory)
        try:
            if isinstance(assets, basestring):
                assets = glob.glob(assets)
            for asset in assets:
                os.system('cp -r %s %s' % (quote(asset), quote(os.path.join(chdir, asset))))
        finally:
            os.chdir(cwd)


def run(filename, d, assets=None):
    exec prepare_stdlib_test(filename, assets) in d
