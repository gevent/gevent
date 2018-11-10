from __future__ import print_function
import os
import unittest

import gevent
from gevent import core


@unittest.skipUnless(
    getattr(core, 'LIBEV_EMBED', False),
    "Needs embedded libev. "
    "hub.loop.fileno is only defined when "
    "we embed libev for some reason. "
    "Choosing specific backends is also only supported by libev "
    "(not libuv), and besides, libuv has a nasty tendency to "
    "abort() the process if its FD gets closed. "
)
class Test(unittest.TestCase):
    # NOTE that we extend unittest.TestCase, not greentest.TestCase
    # Extending the later causes the wrong hub to get used.

    assertRaisesRegex = getattr(unittest.TestCase, 'assertRaisesRegex',
                                getattr(unittest.TestCase, 'assertRaisesRegexp'))

    def _check_backend(self, backend):
        hub = gevent.get_hub(backend, default=False)
        try:
            self.assertEqual(hub.loop.backend, backend)

            gevent.sleep(0.001)
            fileno = hub.loop.fileno()
            if fileno is None:
                raise unittest.SkipTest("backend %s lacks fileno" % (backend,))

            os.close(fileno)
            with self.assertRaisesRegex(SystemError, "(libev)"):
                gevent.sleep(0.001)

            hub.destroy()
            self.assertIn('destroyed', repr(hub))
        finally:
            if hub.loop is not None:
                hub.destroy()

    def _make_test(count, backend): # pylint:disable=no-self-argument
        def test(self):
            self._check_backend(backend)
        test.__name__ = 'test_' + backend + '_' + str(count)
        return test.__name__, test

    count = backend = None
    for count in range(2):
        for backend in core.supported_backends():
            name, func = _make_test(count, backend)
            locals()[name] = func
            name = func = None

    del count
    del backend
    del _make_test

if __name__ == '__main__':
    unittest.main()
