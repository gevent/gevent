from __future__ import print_function
import os
import sys
import tempfile
import gc
import greentest
import gevent
from gevent.fileobject import FileObject, FileObjectThread


PYPY = hasattr(sys, 'pypy_version_info')


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
        ts = type(s)
        s.write(b'x')
        try:
            s.flush()
        except IOError:
            # Sometimes seen on Windows/AppVeyor
            print("Failed flushing fileobject", repr(s), file=sys.stderr)
            import traceback
            traceback.print_exc()

        del s # Deliberately getting ResourceWarning with FileObject(Thread) under Py3
        gc.collect() # PyPy

        if kwargs.get("close", True):
            try:
                os.close(w)
            except (OSError, IOError):
                pass  # expected, because FileObject already closed it
            else:
                raise AssertionError('os.close(%r) must not succeed on %r' % (w, ts))
        else:
            os.close(w)

        fobj = FileObject(r, 'rb')
        self.assertEqual(fobj.read(), b'x')
        fobj.close()

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
            try:
                self._test_del(close=False)
                self.fail("Shouldn't be able to create a FileObjectThread with close=False")
            except TypeError as e:
                self.assertEqual(str(e), 'FileObjectThread does not support close=False on an fd.')

    def test_newlines(self):
        r, w = os.pipe()
        lines = [b'line1\n', b'line2\r', b'line3\r\n', b'line4\r\nline5', b'\nline6']
        g = gevent.spawn(writer, FileObject(w, 'wb'), lines)
        try:
            fobj = FileObject(r, 'rU')
            result = fobj.read()
            fobj.close()
            self.assertEqual('line1\nline2\nline3\nline4\nline5\nline6', result)
        finally:
            g.kill()

    def test_seek(self):
        fileno, path = tempfile.mkstemp()

        s = b'a' * 1024
        os.write(fileno, b'B' * 15)
        os.write(fileno, s)
        os.close(fileno)
        try:
            with open(path, 'rb') as f:
                f.seek(15)
                native_data = f.read(1024)

            with open(path, 'rb') as f_raw:
                f = FileObject(f_raw, 'rb')
                if hasattr(f, 'seekable'):
                    # Py3
                    self.assertTrue(f.seekable())
                f.seek(15)
                self.assertEqual(15, f.tell())
                fileobj_data = f.read(1024)

            self.assertEqual(native_data, s)
            self.assertEqual(native_data, fileobj_data)
        finally:
            os.remove(path)

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
        assert hasattr(x, 'read1'), x
        x.close()
        y.close()

    #if FileObject is not FileObjectThread:
    def test_bufsize_0(self):
        # Issue #840
        r, w = os.pipe()
        x = FileObject(r, 'rb', bufsize=0)
        y = FileObject(w, 'wb', bufsize=0)
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
