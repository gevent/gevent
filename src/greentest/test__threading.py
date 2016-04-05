from gevent import monkey; monkey.patch_all()
import gevent.hub

# check that the locks initialized by 'threading' did not init the hub
assert gevent.hub._get_hub() is None, 'monkey.patch_all() should not init hub'

import gevent
import greentest
import threading


def helper():
    threading.currentThread()
    gevent.sleep(0.2)


class Test(greentest.TestCase):

    def test(self):
        before = len(threading._active)
        g = gevent.spawn(helper)
        gevent.sleep(0.1)
        self.assertEqual(len(threading._active), before + 1)
        g.join()
        self.assertEqual(len(threading._active), before)


if __name__ == '__main__':
    greentest.main()
