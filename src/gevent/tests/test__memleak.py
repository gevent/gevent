import sys
import unittest

from gevent.testing import TestCase, main
import gevent
from gevent.timeout import Timeout

@unittest.skipUnless(
    hasattr(sys, 'gettotalrefcount'),
    "Needs debug build"
)
class TestQueue(TestCase): # pragma: no cover
    # pylint:disable=bare-except,no-member

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

        _, b, c = result.split()
        assert b == c, 'total refcount mismatch: %s' % result



if __name__ == '__main__':
    main()
