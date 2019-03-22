
import sys
import gevent.testing as greentest
try:
    import selectors # Do this before the patch, just to force it
except ImportError:
    pass
from gevent.monkey import patch_all
patch_all()

if sys.platform != 'win32' and greentest.PY3:

    class TestSelectors(greentest.TestCase):

        def test_selectors_select_is_patched(self):
            # https://github.com/gevent/gevent/issues/835
            _select = selectors.SelectSelector._select
            self.assertTrue(hasattr(_select, '_gevent_monkey'), dir(_select))


if __name__ == '__main__':
    greentest.main()
