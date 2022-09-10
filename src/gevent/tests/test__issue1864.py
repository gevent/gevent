import math
import unittest

from gevent.testing import PY39


class TestSubnormalFloatsAreNotDisabled(unittest.TestCase):
    """
    Enabling the -Ofast compiler flag resulted in subnormal floats getting
    disabled the moment when gevent was imported. This impacted libraries
    that expect subnormal floats to be enabled.
    """
    @unittest.skipUnless(PY39, "Need math.nextafter()")
    def test_subnormal_is_not_zero(self):
        import gevent

        assert math.nextafter(0, 1) != 0


if __name__ == "__main__":
    unittest.main()
