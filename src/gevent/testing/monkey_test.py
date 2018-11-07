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

from gevent import monkey
monkey.patch_all(**kwargs)

from .sysinfo import RUNNING_ON_APPVEYOR
from .sysinfo import PY37
from .patched_tests_setup import disable_tests_in_source
try:
    from test import support
except ImportError:
    from test import test_support as support
support.is_resource_enabled = lambda *args: True
del support.use_resources
if RUNNING_ON_APPVEYOR and PY37:
    # 3.7 added a stricter mode for thread cleanup.
    # It appears to be unstable on Windows (at least appveyor)
    # and test_socket.py constantly fails with an extra thread
    # on some random test. We disable it entirely.
    import contextlib
    @contextlib.contextmanager
    def wait_threads_exit(timeout=None): # pylint:disable=unused-argument
        yield
    support.wait_threads_exit = wait_threads_exit


__file__ = os.path.join(os.getcwd(), test_filename)

test_name = os.path.splitext(test_filename)[0]

# It's important that the `module_source` be a native
# string. Passing unicode to `compile` on Python 2 can
# do bad things: it conflicts with a 'coding:' directive,
# and it can cause some TypeError with string literals
if sys.version_info[0] >= 3:
    module_file = open(test_filename, encoding='utf-8')
else:
    module_file = open(test_filename)
with module_file:
    module_source = module_file.read()
module_source = disable_tests_in_source(module_source, test_name)

# We write the module source to a file so that tracebacks
# show correctly, since disabling the tests changes line
# numbers. However, note that __file__ must still point to the
# real location so that data files can be found.
# See https://github.com/gevent/gevent/issues/1306
import tempfile
temp_handle, temp_path = tempfile.mkstemp(prefix=test_name, suffix='.py', text=True)
os.write(temp_handle,
         module_source.encode('utf-8') if not isinstance(module_source, bytes) else module_source)
os.close(temp_handle)
try:
    module_code = compile(module_source,
                          temp_path,
                          'exec',
                          dont_inherit=True)
    exec(module_code, globals())
finally:
    os.remove(temp_path)
