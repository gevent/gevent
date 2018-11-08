#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

if __name__ == '__main__':
    # We expect to be running in this directory, to do test discovery
    # etc, automatically.
    import os
    import os.path
    this_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(this_dir)

    # We also expect this directory to be on the path, because we
    # try to import some test files by their bare name
    import sys
    sys.path.append(this_dir)

    from gevent.testing import testrunner
    testrunner.main()
