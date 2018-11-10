import sys
import unittest

@unittest.skipUnless(
    sys.version_info[0] == 2,
    "Only on Python 2"
)
class Test(unittest.TestCase):

    def test(self):
        import threading
        import gevent.monkey
        gevent.monkey.patch_all()
        import gevent

        self.assertIs(threading._sleep, gevent.sleep)

if __name__ == '__main__':
    unittest.main()
