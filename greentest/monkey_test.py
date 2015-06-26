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

if hasattr(sys, 'pypy_version_info') and sys.pypy_version_info[:3] < (2, 6, 0):
    # PyPy 2.5.0 has issues running these tests if subprocess is
    # patched due to different parameter lists; later versions,
    # specifically 2.6.0 on OS X, have not been shown to have these issues.
    # Travis CI uses 2.5.0 at this writing.

    # Example issue:
    #   ======================================================================
    #   ERROR: test_preexec_errpipe_does_not_double_close_pipes (__main__.POSIXProcessTestCase)
    #   Issue16140: Don't double close pipes on preexec error.
    #   ----------------------------------------------------------------------
    #   Traceback (most recent call last):
    #     File "test_subprocess.py", line 860, in test_preexec_errpipe_does_not_double_close_pipes
    #       stderr=subprocess.PIPE, preexec_fn=raise_it)
    #     File "test_subprocess.py", line 819, in __init__
    #       subprocess.Popen.__init__(self, *args, **kwargs)
    #     File "/home/travis/build/gevent/gevent/gevent/subprocess.py", line 243, in __init__
    #       errread, errwrite)
    #   TypeError: _execute_child() takes exactly 18 arguments (17 given)
    if test_filename in ('test_signal.py', 'test_subprocess.py'):
        kwargs['subprocess'] = False

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
