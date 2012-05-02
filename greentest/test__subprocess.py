import sys
import os
import greentest
import time
from gevent import subprocess, sleep


class Test(greentest.TestCase):

    def test_exit(self):
        popen = subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(10)'])
        self.assertEqual(popen.wait(), 10)

    def test_child_exception(self):
        try:
            subprocess.Popen(['*']).wait()
        except OSError, ex:
            assert ex.errno == 2, ex
        else:
            raise AssertionError('Expected OSError: [Errno 2] No such file or directory')

    if os.path.exists('/proc'):
        def test_leak(self):
            fd_directory = '/proc/%d/fd' % os.getpid()
            num_before = len(os.listdir(fd_directory))
            p = subprocess.Popen([sys.executable, "-c", "print()"],
                                 stdout=subprocess.PIPE)
            p.wait()
            del p
            num_after = len(os.listdir(fd_directory))
            self.assertEqual(num_before, num_after)

    def test_communicate(self):
        p = subprocess.Popen([sys.executable, "-c",
                          'import sys,os;'
                          'sys.stderr.write("pineapple");'
                          'sys.stdout.write(sys.stdin.read())'],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate("banana")
        self.assertEqual(stdout, "banana")
        self.assertEqual(stderr, "pineapple")


if __name__ == '__main__':
    greentest.main()
