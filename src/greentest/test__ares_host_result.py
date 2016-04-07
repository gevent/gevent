from __future__ import print_function

import pickle
import sys
import greentest
try:
    from gevent.ares import ares_host_result
except ImportError as ex:
    print(ex)
    sys.exit(0)


class TestPickle(greentest.TestCase):
    # Issue 104: ares.ares_host_result unpickleable

    def _test(self, protocol):
        r = ares_host_result('family', ('arg1', 'arg2', ))
        dumped = pickle.dumps(r, protocol)
        loaded = pickle.loads(dumped)
        assert r == loaded, (r, loaded)
        assert r.family == loaded.family, (r, loaded)

for i in range(0, pickle.HIGHEST_PROTOCOL):
    def make_test(j):
        return lambda self: self._test(j)
    setattr(TestPickle, 'test' + str(i), make_test(i))


if __name__ == '__main__':
    greentest.main()
