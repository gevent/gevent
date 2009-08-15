from time import time
from gevent import select
import greentest


class TestSelect(greentest.TestCase):

    def test_timeout(self):
        start = time()
        select.select([], [], [], 0.1)
        delay = time() - start
        assert 0.1 - 0.02 < delay < 0.1 + 0.02, delay


if __name__=='__main__':
    greentest.main()
