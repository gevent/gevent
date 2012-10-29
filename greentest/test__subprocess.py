# mostly tests from test_subprocess.py that used to have problems
import sys
import os
import errno
import greentest
import gevent
from gevent import subprocess
import time


if subprocess.mswindows:
    SETBINARY = 'import msvcrt; msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY);'
else:
    SETBINARY = ''


class Test(greentest.TestCase):

    def test_exit(self):
        popen = subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(10)'])
        self.assertEqual(popen.wait(), 10)

    def test_wait(self):
        popen = subprocess.Popen([sys.executable, '-c', 'import sys; sys.exit(11)'])
        gevent.wait([popen])
        self.assertEqual(popen.poll(), 11)

    def test_child_exception(self):
        try:
            subprocess.Popen(['*']).wait()
        except OSError, ex:
            assert ex.errno == 2, ex
        else:
            raise AssertionError('Expected OSError: [Errno 2] No such file or directory')

    def test_leak(self):
        num_before = greentest.get_number_open_files()
        p = subprocess.Popen([sys.executable, "-c", "print()"],
                             stdout=subprocess.PIPE)
        p.wait()
        del p
        num_after = greentest.get_number_open_files()
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
        if sys.executable.endswith('-dbg'):
            assert stderr.startswith('pineapple')
        else:
            self.assertEqual(stderr, "pineapple")

    def test_universal1(self):
        p = subprocess.Popen([sys.executable, "-c",
                             'import sys,os;' + SETBINARY +
                             'sys.stdout.write("line1\\n");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line2\\r");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line3\\r\\n");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line4\\r");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("\\nline5");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("\\nline6");'],
                             stdout=subprocess.PIPE,
                             universal_newlines=1)
        try:
            stdout = p.stdout.read()
            if hasattr(file, 'newlines'):
                # Interpreter with universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\nline3\nline4\nline5\nline6")
            else:
                # Interpreter without universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\rline3\r\nline4\r\nline5\nline6")
        finally:
            p.stdout.close()

    def test_universal2(self):
        p = subprocess.Popen([sys.executable, "-c",
                             'import sys,os;' + SETBINARY +
                             'sys.stdout.write("line1\\n");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line2\\r");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line3\\r\\n");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("line4\\r\\nline5");'
                             'sys.stdout.flush();'
                             'sys.stdout.write("\\nline6");'],
                             stdout=subprocess.PIPE,
                             universal_newlines=1)
        try:
            stdout = p.stdout.read()
            if hasattr(file, 'newlines'):
                # Interpreter with universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\nline3\nline4\nline5\nline6")
            else:
                # Interpreter without universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\rline3\r\nline4\r\nline5\nline6")
        finally:
            p.stdout.close()

    if sys.platform != 'win32':

        def test_nonblock_removed(self):
            # see issue #134
            r, w = os.pipe()
            p = subprocess.Popen(['grep', 'text'], stdin=subprocess.FileObject(r))
            try:
                os.close(w)
                time.sleep(0.1)
                self.assertEqual(p.poll(), None)
            finally:
                if p.poll() is None:
                    p.kill()

    def test_issue148(self):
        for i in range(7):
            try:
                p1 = subprocess.Popen('this_name_must_not_exist')
            except OSError:
                ex = sys.exc_info()[1]
                if ex.errno != errno.ENOENT:
                    raise
            else:
                raise AssertionError('must fail with ENOENT')


if __name__ == '__main__':
    greentest.main()
