# mostly tests from test_subprocess.py that used to have problems
import sys
import six
import os
import errno
import greentest
import gevent
from gevent import subprocess
import time
import gc


PYPY = hasattr(sys, 'pypy_version_info')


if subprocess.mswindows:
    SETBINARY = 'import msvcrt; msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY);'
else:
    SETBINARY = ''


python_universal_newlines = hasattr(sys.stdout, 'newlines')


class Test(greentest.TestCase):

    def setUp(self):
        gc.collect()
        gc.collect()

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
        except OSError as ex:
            assert ex.errno == 2, ex
            if six.PY3:
                ex.__traceback__ = None
        else:
            raise AssertionError('Expected OSError: [Errno 2] No such file or directory')

    def test_leak(self):
        num_before = greentest.get_number_open_files()
        p = subprocess.Popen([sys.executable, "-c", "print()"],
                             stdout=subprocess.PIPE)
        p.wait()
        del p
        if PYPY:
            gc.collect()
            gc.collect()
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
        (stdout, stderr) = p.communicate(b"banana")
        self.assertEqual(stdout, b"banana")
        if sys.executable.endswith('-dbg'):
            assert stderr.startswith(b'pineapple')
        else:
            self.assertEqual(stderr, b"pineapple")

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
            if python_universal_newlines:
                # Interpreter with universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\nline3\nline4\nline5\nline6")
            else:
                # Interpreter without universal newline support
                self.assertEqual(stdout,
                                 b"line1\nline2\rline3\r\nline4\r\nline5\nline6")
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
            if python_universal_newlines:
                # Interpreter with universal newline support
                self.assertEqual(stdout,
                                 "line1\nline2\nline3\nline4\nline5\nline6")
            else:
                # Interpreter without universal newline support
                self.assertEqual(stdout,
                                 b"line1\nline2\rline3\r\nline4\r\nline5\nline6")
        finally:
            p.stdout.close()

    if sys.platform != 'win32':

        def test_nonblock_removed(self):
            import subprocess as orig_subprocess
            r, w = os.pipe()
            p = orig_subprocess.Popen(['grep', 'text'], stdin=r)
            try:
                os.close(w)
                time.sleep(0.1)
                expected = p.poll()
            finally:
                if p.poll() is None:
                    p.kill()

            # see issue #134
            r, w = os.pipe()
            p = subprocess.Popen(['grep', 'text'], stdin=subprocess.FileObject(r))
            try:
                os.close(w)
                time.sleep(0.1)
                self.assertEqual(p.poll(), expected)
            finally:
                if p.poll() is None:
                    p.kill()

    def test_issue148(self):
        for i in range(7):
            try:
                subprocess.Popen('this_name_must_not_exist')
            except OSError as ex:
                if ex.errno != errno.ENOENT:
                    raise
                if six.PY3:
                    ex.__traceback__ = None
            else:
                raise AssertionError('must fail with ENOENT')

    def test_check_output_keyword_error(self):
        try:
            subprocess.check_output([sys.executable, '-c', 'import sys; sys.exit(44)'])
        except subprocess.CalledProcessError as e:
            self.assertEqual(e.returncode, 44)
            if six.PY3:
                e.__traceback__ = None
        else:
            raise AssertionError('must fail with CalledProcessError')


if __name__ == '__main__':
    greentest.main()
