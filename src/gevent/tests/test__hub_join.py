import unittest

import gevent

class Test(unittest.TestCase):

    def test(self):
        # hub.join() guarantees that loop has exited cleanly
        res = gevent.get_hub().join()
        self.assertTrue(res)

        res = gevent.get_hub().join()
        self.assertTrue(res)

        # but it is still possible to use gevent afterwards
        gevent.sleep(0.01)

        res = gevent.get_hub().join()
        self.assertTrue(res)


if __name__ == '__main__':
    unittest.main()
