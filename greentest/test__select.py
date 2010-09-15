from time import time
from gevent import select
import greentest


class TestSelect(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)


class TestSelectTypes(greentest.TestCase):

    def test(self):
        select.select([1], [], [], 0.001)
        select.select([1L], [], [], 0.001)


if __name__ == '__main__':
    greentest.main()
