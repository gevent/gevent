import unittest
import time
import gevent
from gevent.hub import get_hub


class TestShutdown(unittest.TestCase):

    def _shutdown(self, seconds=0, fuzzy=None):
        if fuzzy is None:
            fuzzy = max(0.05, seconds / 2.)
        start = time.time()
        get_hub().join()
        delta = time.time() - start
        assert seconds - fuzzy < delta < seconds + fuzzy, (seconds - fuzzy, delta, seconds + fuzzy)

    def assert_hub(self):
        assert 'hub' in gevent.hub._threadlocal.__dict__

    def assert_no_hub(self):
        assert 'hub' not in gevent.hub._threadlocal.__dict__, gevent.hub._threadlocal.__dict__

    def test(self):
        # make sure Hub is started. For the test case when hub is not started, see test_hub_shutdown.py
        gevent.sleep(0)
        assert not gevent.hub.get_hub().dead
        self._shutdown()
        self.assert_no_hub()

        # shutting down dead hub is silent
        self._shutdown()
        self._shutdown()
        self.assert_no_hub()

        # ressurect
        gevent.sleep(0)
        self.assert_hub()

        t = get_hub().loop.timer(0.1)
        t.start(lambda: None)
        self.assert_hub()
        self._shutdown(seconds=0.1)
        self.assert_no_hub()
        self._shutdown(seconds=0)
        self.assert_no_hub()


if __name__ == '__main__':
    unittest.main()
