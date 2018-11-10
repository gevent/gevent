import unittest
import warnings

from gevent.testing.modules import walk_modules
from gevent.testing import main
from gevent.testing.sysinfo import NON_APPLICABLE_SUFFIXES


from gevent.testing import six


class TestExec(unittest.TestCase):
    pass


def make_exec_test(path, module):

    def test(_):
        with open(path, 'rb') as f:
            src = f.read()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            six.exec_(src, {'__file__': path})

    name = "test_" + module.replace(".", "_")
    test.__name__ = name
    setattr(TestExec, name, test)

def make_all_tests():
    for path, module in walk_modules(recursive=True):
        if module.endswith(NON_APPLICABLE_SUFFIXES):
            continue
        make_exec_test(path, module)


make_all_tests()

if __name__ == '__main__':
    main()
