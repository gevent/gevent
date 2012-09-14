from gevent import monkey; monkey.patch_all()

import sys
import os
from patched_tests_setup import disable_tests_in_source
import test.test_support
test.test_support.is_resource_enabled = lambda *args: True
del test.test_support.use_resources

test_filename = sys.argv[1]
del sys.argv[1]
__file__ = os.path.join(os.getcwd(), test_filename)

test_name = os.path.splitext(test_filename)[0]

module_source = open(test_filename).read()
module_source = disable_tests_in_source(module_source, test_name)
module_code = compile(module_source, test_filename, 'exec')


if test_name.startswith('test_urllib2'):
    import test
    import test_cookielib
    import test_urllib2
    test.test_urllib2 = test_urllib2
    sys.modules['test.test_urllib2'] = test_urllib2
    sys.modules['test.test_cookielib'] = test_cookielib
elif test_name == 'test_threading':
    import test
    import lock_tests
    test.lock_tests = lock_tests


exec module_code in globals()
