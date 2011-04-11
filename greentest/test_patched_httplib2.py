# run test_httplib.py with gevent.httplib
import helper
exec helper.prepare_stdlib_test('test_httplib.py', httplib=True) in globals()
