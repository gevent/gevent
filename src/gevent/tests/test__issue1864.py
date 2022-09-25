import sys
import unittest


class TestSubnormalFloatsAreNotDisabled(unittest.TestCase):
    """
    Enabling the -Ofast compiler flag resulted in subnormal floats getting
    disabled the moment when gevent was imported. This impacted libraries
    that expect subnormal floats to be enabled.
    """
    def test_subnormal_is_not_zero(self):
        import gevent

        # `sys.float_info.min` is the minimum representable positive normalized
        # float, so dividing it by two gives us a positive subnormal float,
        # as long as subnormals floats are not disabled.
        assert (sys.float_info.min / 2) > 0


if __name__ == "__main__":
    unittest.main()
