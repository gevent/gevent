import sys
import greentest
import gevent
from gevent.hub import get_hub


def raise_(ex):
    raise ex


MSG = 'should be re-raised and caught'


class Test(greentest.TestCase):
    x = None
    error_fatal = False

    def start(self, *args):
        raise NotImplementedError

    def setUp(self):
        self.x = None

    def test_sys_exit(self):
        self.start(sys.exit, MSG)

        try:
            gevent.sleep(0.001)
        except SystemExit as ex:
            assert str(ex) == MSG, repr(str(ex))
        else:
            raise AssertionError('must raise SystemExit')

    def test_keyboard_interrupt(self):
        self.start(raise_, KeyboardInterrupt)

        try:
            gevent.sleep(0.001)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError('must raise KeyboardInterrupt')

    def test_keyboard_interrupt_stderr_patched(self):
        from gevent import monkey
        monkey.patch_sys(stdin=False, stdout=False, stderr=True)
        try:
            try:
                self.start(raise_, KeyboardInterrupt)
                while True:
                    gevent.sleep(0.1)
            except KeyboardInterrupt:
                pass # expected
        finally:
            sys.stderr = monkey.get_original('sys', 'stderr')

    def test_system_error(self):
        self.start(raise_, SystemError(MSG))

        try:
            gevent.sleep(0.001)
        except SystemError as ex:
            assert str(ex) == MSG, repr(str(ex))
        else:
            raise AssertionError('must raise SystemError')

    def test_exception(self):
        self.start(raise_, Exception('regular exception must not kill the program'))
        gevent.sleep(0.001)


class TestCallback(Test):

    def tearDown(self):
        if self.x is not None:
            assert not self.x.pending, self.x

    def start(self, *args):
        self.x = get_hub().loop.run_callback(*args)


class TestSpawn(Test):

    def tearDown(self):
        gevent.sleep(0.0001)
        if self.x is not None:
            assert self.x.dead, self.x

    def start(self, *args):
        self.x = gevent.spawn(*args)


del Test

if __name__ == '__main__':
    greentest.main()
