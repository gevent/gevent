import sys
import os

kwargs = {}

if sys.argv[1] == '--Event':
    kwargs['Event'] = True
    del sys.argv[1]
else:
    kwargs['Event'] = False

test_filename = sys.argv[1]
del sys.argv[1]

print('Running with patch_all(%s): %s' % (','.join('%s=%r' % x for x in kwargs.items()), test_filename))

from gevent import monkey; monkey.patch_all(**kwargs)

from patched_tests_setup import disable_tests_in_source
try:
    from test import support
except ImportError:
    from test import test_support as support
support.is_resource_enabled = lambda *args: True
del support.use_resources

if sys.version_info[:2] <= (2, 6):
    support.TESTFN += '_%s' % os.getpid()

__file__ = os.path.join(os.getcwd(), test_filename)

test_name = os.path.splitext(test_filename)[0]
module_source = open(test_filename).read()
module_source = disable_tests_in_source(module_source, test_name)
module_code = compile(module_source, test_filename, 'exec')
exec(module_code, globals())
