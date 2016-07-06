import gevent
import sys
import greentest
import _six as six

if not six.PY3:
    sys.exc_clear()


class ExpectedError(Exception):
    pass


expected_error = ExpectedError('expected exception in hello')


def hello():
    assert sys.exc_info() == (None, None, None), sys.exc_info()
    raise expected_error


def hello2():
    try:
        hello()
    except ExpectedError:
        pass


error = Exception('hello')


class Test(greentest.TestCase):

    def test1(self):
        try:
            raise error
        except:
            self.expect_one_error()
            g = gevent.spawn(hello)
            g.join()
            self.assert_error(ExpectedError, expected_error)
            if not isinstance(g.exception, ExpectedError):
                raise g.exception
            try:
                raise
            except Exception:
                ex = sys.exc_info()[1]
                assert ex is error, (ex, error)

    def test2(self):
        timer = gevent.get_hub().loop.timer(0)
        timer.start(hello2)
        gevent.sleep(0.1)
        assert sys.exc_info() == (None, None, None), sys.exc_info()


if __name__ == '__main__':
    greentest.main()
