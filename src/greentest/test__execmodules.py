from greentest import walk_modules, BaseTestCase, main, NON_APPLICABLE_SUFFIXES
import _six as six


class TestExec(BaseTestCase):
    pass


def make_exec_test(path, module):

    def test(self):
        #sys.stderr.write('%s %s\n' % (module, path))
        with open(path, 'rb') as f:
            src = f.read()
        six.exec_(src, {'__file__': path})

    name = "test_" + module.replace(".", "_")
    test.__name__ = name
    setattr(TestExec, name, test)


for path, module in walk_modules():
    ignored = False
    for x in NON_APPLICABLE_SUFFIXES:
        if module.endswith(x):
            ignored = True
            break
    if ignored:
        continue

    make_exec_test(path, module)


if __name__ == '__main__':
    main()
