
try:
    # Do this before the patch to be sure we clean
    # things up properly if the order is wrong.
    import selectors
except ImportError:
    selectors = None
import socket

import gevent

from gevent.monkey import patch_all
import gevent.testing as greentest

patch_all()

@greentest.skipIf(
    selectors is None,
    "selectors module not present"
)
class TestSelectors(greentest.TestCase):

    @greentest.skipOnWindows(
        "SelectSelector._select is a normal function on Windows"
    )
    def test_selectors_select_is_patched(self):
        # https://github.com/gevent/gevent/issues/835
        _select = selectors.SelectSelector._select
        self.assertIn('_gevent_monkey', dir(_select))

    @greentest.skipUnless(
        hasattr(selectors, 'PollSelector'),
        "Needs gevent.select.poll"
    )
    def test_poll_is_default(self):
        # Depending on the order of imports, gevent.select.poll may be defined but
        # selectors.PollSelector may not be defined.
        # https://github.com/gevent/gevent/issues/1466
        self.assertIs(selectors.DefaultSelector, selectors.PollSelector)

    def _check_selector(self, sel):
        def read(conn, _mask):
            data = conn.recv(100)  # Should be ready
            if data:
                conn.send(data)  # Hope it won't block

            sel.unregister(conn)
            conn.close()

        def run_selector_once():
            events = sel.select()
            for key, mask in events:
                key.data(key.fileobj, mask)

        sock1, sock2 = socket.socketpair()
        try:
            sel.register(sock1, selectors.EVENT_READ, read)
            glet = gevent.spawn(run_selector_once)
            DATA = b'abcdef'
            sock2.send(DATA)
            data = sock2.recv(50)
            self.assertEqual(data, DATA)
        finally:
            sel.close()
            sock1.close()
            sock2.close()
            glet.join(10)
        self.assertTrue(glet.ready())


    def _make_test(name, kind): # pylint:disable=no-self-argument
        if kind is None:
            def m(self):
                self.skipTest(name + ' is not defined')
        else:
            def m(self, k=kind):
                sel = k()
                self._check_selector(sel)
        m.__name__ = 'test_selector_' + name
        return m

    SelKind = SelKindName = None
    for SelKindName in (
            # The subclass hierarchy changes between versions, and is
            # complex (e.g, BaseSelector <- BaseSelectorImpl <-
            # _PollLikSelector <- PollSelector) so its easier to check against
            # names.
            'KqueueSelector',
            'EpollSelector',
            'DevpollSelector',
            'PollSelector',
            'SelectSelector',
    ):
        SelKind = getattr(selectors, SelKindName, None)
        m = _make_test(SelKindName, SelKind)
        locals()[m.__name__] = m

    del SelKind
    del SelKindName
    del _make_test


if __name__ == '__main__':
    greentest.main()
