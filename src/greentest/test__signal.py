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
            assert sig.ref is False, repr(sig.ref)
            sig.ref = True
            assert sig.ref is True
            sig.ref = False
            try:
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected as ex:
                    assert str(ex) == 'TestSignal', ex
                # also let's check that alarm is persistent
                signal.alarm(1)
                try:
                    gevent.sleep(2)
                    raise AssertionError('must raise Expected')
                except Expected as ex:
                    assert str(ex) == 'TestSignal', ex
            finally:
                sig.cancel()


if __name__ == '__main__':
    greentest.main()
