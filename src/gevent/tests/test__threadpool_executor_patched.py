from gevent import monkey; monkey.patch_all()

import gevent.testing as greentest

from . import test__threadpool


class TestPatchedTPE(test__threadpool.TestTPE): # pylint:disable=too-many-ancestors
    MONKEY_PATCHED = True


if __name__ == '__main__':
    greentest.main()
