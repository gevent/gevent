import sys
import os
import unittest
import glob
import re
from os.path import abspath, dirname, join, basename

# this regex matches filenames of the standard tests (with one underscore)
stdtest_re = re.compile('^(test_[^_].+|lock_tests)\.py$')

script = 'pep8'

try:
    index = sys.argv.index('--script')
except ValueError:
    pass
else:
    script = sys.argv[index + 1]
    del sys.argv[index:index + 2]


# E501 line too long (80 character limit that we don't follow)
command = script + ' --repeat --statistics --ignore E501 %s | grep -v E501'


if os.system('pep8 --version'):
    sys.stderr.write('Please install pep8 script\n')
    sys.exit(0)


def system(*args):
    command = ' '.join(args)
    popen_result = os.popen(command)
    result = popen_result.read()
    if result:
        sys.stderr.write(result)
        raise AssertionError('"%s" failed' % str(command)[:100])


class Test(unittest.TestCase):

    def test_gevent(self):
        import gevent
        # E221 multiple spaces before operator
        system(command % abspath(dirname(gevent.__file__)), '| grep -v E221')

    def test_tests(self):
        # E702 multiple statements on one line (from gevent import monkey; monkey.patch_all())
        files = glob.glob(join(abspath(dirname(__file__)), '*.py'))
        # filter out standard tests of form test_xxx.py (one underscore)
        files = [filename for filename in files if stdtest_re.match(basename(filename)) is None]
        system(command % (' '.join(files)), '| grep -v E702')

    # we keep the standard tests as close to the originals as possible, so don't test them
    def X_test_std_tests(self):
        # E702 multiple statements on one line (from gevent import monkey; monkey.patch_all())
        files = glob.glob(join(abspath(dirname(__file__)), '*.py'))
        # only count standard tests of form test_xxx.py (one underscore)
        files = [filename for filename in files if stdtest_re.match(basename(filename)) is not None]
        system(command % (' '.join(files)), '| grep -v E702')

    def test_examples(self):
        # E702 multiple statements on one line (from gevent import monkey; monkey.patch_all())
        # E202 whitespace before '('
        system(command % join(dirname(abspath(dirname(__file__))), 'examples'), '| grep -v E702 | grep -v E202')

    def test_doc(self):
        system(command % join(dirname(abspath(dirname(__file__))), 'doc'))

    def test_setup(self):
        system(command % join(dirname(abspath(dirname(__file__))), 'setup.py'))


if __name__ == '__main__':
    unittest.main()
