from time import time
from gevent import select
import greentest


class TestSelect(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)


if __name__=='__main__':
    greentest.main()
