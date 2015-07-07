import sys
from gevent.hub import PYGTE279
from greentest import walk_modules, BaseTestCase, main
import six


class TestExec(BaseTestCase):
    pass


def make_exec_test(path, module):

    def test(self):
        #sys.stderr.write('%s %s\n' % (module, path))
        with open(path, 'rb') as f:
            src = f.read()
        six.exec_(src, {})

    name = "test_" + module.replace(".", "_")
    test.__name__ = name
    setattr(TestExec, name, test)


for path, module in walk_modules():
    if sys.version_info[0] == 3 and path.endswith('2.py'):
        continue
    if sys.version_info[0] == 2 and path.endswith('3.py'):
        continue
    if not PYGTE279 and path.endswith('279.py'):
        continue
    make_exec_test(path, module)


if __name__ == '__main__':
    main()
