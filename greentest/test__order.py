import gevent
import greentest


class appender(object):

    def __init__(self, lst, item):
        self.lst = lst
        self.item = item

    def __call__(self, *args):
        self.lst.append(self.item)


class Test(greentest.TestCase):

    count = 2

    def test_greenlet_link(self):
        lst = []

        # test that links are executed in the same order as they were added
        g = gevent.spawn(lst.append, 0)

        for i in xrange(1, self.count):
            g.link(appender(lst, i))
        g.join()
        self.assertEqual(lst, range(self.count))


class Test3(Test):
    count = 3


class Test4(Test):
    count = 4


class TestM(Test):
    count = 1000


if __name__ == '__main__':
    greentest.main()
