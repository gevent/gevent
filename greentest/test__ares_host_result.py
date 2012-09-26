import pickle
import greentest
from gevent.ares import ares_host_result


class TestPickle(greentest.TestCase):
    # Issue 104: ares.ares_host_result unpickleable

    def _test(self, protocol):
        r = ares_host_result('family', ('arg1', 'arg2', ))
        dumped = pickle.dumps(r, protocol)
        loaded = pickle.loads(dumped)
        assert r == loaded, (r, loaded)
        assert r.family == loaded.family, (r, loaded)

    def test0(self):
        return self._test(0)

    def test1(self):
        return self._test(1)

    def test2(self):
        return self._test(2)

    if pickle.HIGHEST_PROTOCOL == 3:
        def test3(self):
            return self._test(3)
    else:
        assert pickle.HIGHEST_PROTOCOL == 2, pickle.HIGHEST_PROTOCOL


if __name__ == '__main__':
    greentest.main()
