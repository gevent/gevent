import gevent
import sys


def hello():
    assert sys.exc_info() == (None, None, None), sys.exc_info()

error = Exception('hello')

try:
    raise error
except:
    gevent.spawn(hello).join()
    try:
        raise
    except Exception, ex:
        assert ex is error, (ex, error)
