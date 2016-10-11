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

        def test_handler(self):
            self.assertRaises(TypeError, gevent.signal, signal.SIGALRM, 1)

        def test_alarm(self):
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

        @greentest.ignores_leakcheck
        def test_reload(self):
            # The site module tries to set attributes
            # on all the modules that are loaded (specifically, __file__).
            # If gevent.signal is loaded, and is our compatibility shim,
            # this used to fail on Python 2: sys.modules['gevent.signal'] has no
            # __loader__ attribute, so site.py's main() function tries to do
            # gevent.signal.__file__ = os.path.abspath(gevent.signal.__file__), which
            # used to not be allowed. (Under Python 3, __loader__ is present so this
            # doesn't happen). See
            # https://github.com/gevent/gevent/issues/805

            import gevent.signal # make sure it's in sys.modules pylint:disable=redefined-outer-name
            assert gevent.signal
            import site
            if greentest.PY34:
                from importlib import reload as reload_module
            elif greentest.PY3:
                from imp import reload as reload_module
            else:
                # builtin on py2
                reload_module = reload # pylint:disable=undefined-variable

            try:
                reload_module(site)
            except TypeError:
                assert greentest.PY36
                assert greentest.RUNNING_ON_CI
                import sys
                for m in set(sys.modules.values()):
                    try:
                        if m.__cached__ is None:
                            print("Module has None __cached__", m)
                    except AttributeError:
                        continue

if __name__ == '__main__':
    greentest.main()
