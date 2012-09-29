from greentest import walk_modules, BaseTestCase, main
import six


class TestExec(BaseTestCase):
    pass


def make_exec_test(path, module):

    def test(self):
        #sys.stderr.write('%s %s\n' % (module, path))
        f = open(path)
        src = f.read()
        f.close()
        six.exec_(src, {})

    name = "test_" + module.replace(".", "_")
    test.__name__ = name
    setattr(TestExec, name, test)


for path, module in walk_modules():
    make_exec_test(path, module)


if __name__ == '__main__':
    main()
