from __future__ import print_function
from gevent import monkey; monkey.patch_all()

import gevent.testing as greentest
import gevent.threadpool


if hasattr(gevent.threadpool, 'ThreadPoolExecutor'):

    from test__threadpool import TestTPE as _Base

    class TestPatchedTPE(_Base):
        MONKEY_PATCHED = True

    del _Base

if __name__ == '__main__':
    greentest.main()
