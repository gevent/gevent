import gevent
import sys
import greentest

sys.exc_clear()


class ExpectedError(Exception):
    pass


expected_error = ExpectedError('expected exception in hello')


def hello():
    assert sys.exc_info() == (None, None, None), sys.exc_info()
    raise expected_error


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
            self.assert_stderr('<Greenlet at 0x[0-9a-f]+L?: hello> failed with ExpectedError')
            if not isinstance(g.exception, ExpectedError):
                raise g.exception
            try:
                raise
            except Exception, ex:
                assert ex is error, (ex, error)

    def test2(self):
        gevent.core.timer(0, hello)
        self.hook_stderr()
        gevent.sleep(0.1)
        self.assert_stderr_traceback(expected_error)
        assert sys.exc_info() == (None, None, None), sys.exc_info()


if __name__ == '__main__':
    greentest.main()
