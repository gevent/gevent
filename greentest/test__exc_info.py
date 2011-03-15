import gevent
import sys
import greentest
from gevent.hub import get_hub

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
            self.hook_stderr()
            g = gevent.spawn(hello)
            g.join()
            self.assert_stderr_traceback(expected_error)
            self.assert_stderr('Ignoring ExpectedError in <Greenlet')
            if not isinstance(g.exception, ExpectedError):
                raise g.exception
            try:
                raise
            except Exception, ex:
                assert ex is error, (ex, error)

    def test2(self):
        timer = get_hub().loop.timer(0)
        timer.start(hello2)
        gevent.sleep(0.1)
        assert sys.exc_info() == (None, None, None), sys.exc_info()


if __name__ == '__main__':
    greentest.main()
