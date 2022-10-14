import sys
import unittest

from gevent.testing import TestCase
import gevent
from gevent.timeout import Timeout

@unittest.skipUnless(
    hasattr(sys, 'gettotalrefcount'),
    "Needs debug build"
)
# XXX: This name makes no sense. What was this for originally?
class TestQueue(TestCase): # pragma: no cover
    # pylint:disable=bare-except,no-member

    def test(self):

        refcounts = []
        for _ in range(15):
            try:
                Timeout.start_new(0.01)
                gevent.sleep(0.1)
                self.fail('must raise Timeout')
            except Timeout:
                pass
            refcounts.append(sys.gettotalrefcount())

        # Refcounts may go down, but not up
        final = refcounts[-1]
        previous = refcounts[-2]
        self.assertLessEqual(
            final, previous,
            "total refcount mismatch: %s" % refcounts)


if __name__ == '__main__':
    unittest.main()
