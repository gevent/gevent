import sys


from greentest import TestCase, main
import gevent
from gevent.timeout import Timeout


class TestQueue(TestCase):

    def test(self):
        result = ''
        try:
            Timeout.start_new(0.01)
            gevent.sleep(1)
            raise AssertionError('must raise Timeout')
        except KeyboardInterrupt:
            raise
        except:
            pass

        result += '%s ' % sys.gettotalrefcount()

        try:
            Timeout.start_new(0.01)
            gevent.sleep(1)
            raise AssertionError('must raise Timeout')
        except KeyboardInterrupt:
            raise
        except:
            pass

        result += '%s ' % sys.gettotalrefcount()

        try:
            Timeout.start_new(0.01)
            gevent.sleep(1)
            raise AssertionError('must raise Timeout')
        except KeyboardInterrupt:
            raise
        except:
            pass

        result += '%s' % sys.gettotalrefcount()

        a, b, c = result.split()
        assert b == c, 'total refcount mismatch: %s' % result


if not hasattr(sys, 'gettotalrefcount'):
    del TestQueue

if __name__ == '__main__':
    main()
