from __future__ import print_function
import os
import sys
import tempfile
import gc

import gevent
from gevent.fileobject import FileObject, FileObjectThread

import greentest
from greentest.sysinfo import PY3
from greentest.flaky import reraiseFlakyTestRaceConditionLibuv
from greentest.skipping import skipOnLibuvOnCIOnPyPy

try:
    ResourceWarning
except NameError:
    class ResourceWarning(Warning):
        "Python 2 fallback"


class Test(greentest.TestCase):

    def _test_del(self, **kwargs):
        pipe = os.pipe()
        try:
            self._do_test_del(pipe, **kwargs)
        finally:
            for f in pipe:
                try:
                    os.close(f)
                except (IOError, OSError):
                    pass

    def _do_test_del(self, pipe, **kwargs):
        r, w = pipe
        s = FileObject(w, 'wb', **kwargs)
        s.write(b'x')
        try:
            s.flush()
        except IOError:
            # Sometimes seen on Windows/AppVeyor
            print("Failed flushing fileobject", repr(s), file=sys.stderr)
            import traceback
            traceback.print_exc()

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', ResourceWarning)
            # Deliberately getting ResourceWarning with FileObject(Thread) under Py3
            del s
            gc.collect() # PyPy

        if kwargs.get("close", True):
            with self.assertRaises((OSError, IOError)):
                # expected, because FileObject already closed it
                os.close(w)
        else:
            os.close(w)

        with FileObject(r, 'rb') as fobj:
            self.assertEqual(fobj.read(), b'x')

    def test_del(self):
        # Close should be true by default
        self._test_del()

    def test_del_close(self):
        self._test_del(close=True)

    if FileObject is not FileObjectThread:
        # FileObjectThread uses os.fdopen() when passed a file-descriptor, which returns
        # an object with a destructor that can't be bypassed, so we can't even
        # create one that way
        def test_del_noclose(self):
            self._test_del(close=False)
    else:
        def test_del_noclose(self):
            with self.assertRaisesRegex(TypeError,
                                        'FileObjectThread does not support close=False on an fd.'):
                self._test_del(close=False)

    def test_newlines(self):
        import warnings
        r, w = os.pipe()
        lines = [b'line1\n', b'line2\r', b'line3\r\n', b'line4\r\nline5', b'\nline6']
        g = gevent.spawn(writer, FileObject(w, 'wb'), lines)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                # U is deprecated in Python 3, shows up on FileObjectThread
                fobj = FileObject(r, 'rU')
            result = fobj.read()
            fobj.close()
            self.assertEqual('line1\nline2\nline3\nline4\nline5\nline6', result)
        finally:
            g.kill()

    @skipOnLibuvOnCIOnPyPy("This appears to crash on libuv/pypy/travis.")
    # No idea why, can't duplicate locally.
    def test_seek(self):
        fileno, path = tempfile.mkstemp('.gevent.test__fileobject.test_seek')
        self.addCleanup(os.remove, path)

        s = b'a' * 1024
        os.write(fileno, b'B' * 15)
        os.write(fileno, s)
        os.close(fileno)

        with open(path, 'rb') as f:
            f.seek(15)
            native_data = f.read(1024)

        with open(path, 'rb') as f_raw:
            try:
                f = FileObject(f_raw, 'rb')
            except ValueError:
                # libuv on Travis can raise EPERM
                # from FileObjectPosix. I can't produce it on mac os locally,
                # don't know what the issue is. This started happening on Jan 19,
                # in the branch that caused all watchers to be explicitly closed.
                # That shouldn't have any effect on io watchers, though, which were
                # already being explicitly closed.
                reraiseFlakyTestRaceConditionLibuv()
            if PY3 or FileObject is not FileObjectThread:
                self.assertTrue(f.seekable())
            f.seek(15)
            self.assertEqual(15, f.tell())
            fileobj_data = f.read(1024)

        self.assertEqual(native_data, s)
        self.assertEqual(native_data, fileobj_data)

    def test_close_pipe(self):
        # Issue #190, 203
        r, w = os.pipe()
        x = FileObject(r)
        y = FileObject(w, 'w')
        x.close()
        y.close()

    def test_read1(self):
        # Issue #840
        r, w = os.pipe()
        x = FileObject(r)
        y = FileObject(w, 'w')
        self._close_on_teardown(x)
        self._close_on_teardown(y)
        self.assertTrue(hasattr(x, 'read1'))

    #if FileObject is not FileObjectThread:
    def test_bufsize_0(self):
        # Issue #840
        r, w = os.pipe()
        x = FileObject(r, 'rb', bufsize=0)
        y = FileObject(w, 'wb', bufsize=0)
        self._close_on_teardown(x)
        self._close_on_teardown(y)
        y.write(b'a')
        b = x.read(1)
        self.assertEqual(b, b'a')

        y.writelines([b'2'])
        b = x.read(1)
        self.assertEqual(b, b'2')

def writer(fobj, line):
    for character in line:
        fobj.write(character)
        fobj.flush()
    fobj.close()


if __name__ == '__main__':
    greentest.main()
