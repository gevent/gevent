from gevent import select
import greentest


class TestSelect(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)


class TestSelectTypes(greentest.TestCase):

    def test_int(self):
        select.select([1], [], [], 0.001)

    def test_long(self):
        select.select([1L], [], [], 0.001)

    def test_string(self):
        self.switch_expected = False
        self.assertRaises(TypeError, select.select, ['hello'], [], [], 0.001)


if __name__ == '__main__':
    greentest.main()
