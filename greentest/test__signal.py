import signal
import greentest
import gevent


class Expected(Exception):
    pass


def raise_Expected():
    raise Expected('TestSignal')


if hasattr(signal, 'SIGALRM'):

    class TestSignal(greentest.TestCase):

        error_fatal = False
        __timeout__ = 5

        def test(self):
            sig = gevent.signal(signal.SIGALRM, raise_Expected)
            try:
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected, ex:
                    assert str(ex) == 'TestSignal', ex
                # also let's check that alarm is persistent
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected, ex:
                    assert str(ex) == 'TestSignal', ex
            finally:
                sig.cancel()


if __name__ == '__main__':
    greentest.main()
