import gevent
import greentest


class Test(greentest.TestCase):

    count = 2

    def setUp(self):
        self.lst = []

    def tearDown(self):
        self.assertEqual(self.lst, range(self.count))

    def test_greenlet_link(self):
        # test that links are executed in the same order as they were added
        g = gevent.spawn(self.lst.append, 0)

        class appender(object):
            def __init__(myself, item):
                myself.item = item
            def __call__(myself, *args):
                self.lst.append(myself.item)

        for i in xrange(1, self.count):
            g.link(appender(i))
        g.join()


class Test3(Test):
    count = 3


class Test4(Test):
    count = 4


class TestM(Test):
    count = 1000


if __name__ == '__main__':
    greentest.main()
