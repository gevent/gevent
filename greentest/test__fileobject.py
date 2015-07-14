import os
import sys
import tempfile
import greentest
import gevent
from gevent.fileobject import FileObject, FileObjectThread


PYPY = hasattr(sys, 'pypy_version_info')


class Test(greentest.TestCase):

    def _test_del(self, **kwargs):
        r, w = os.pipe()
        s = FileObject(w, 'wb')
        s.write(b'x')
        s.flush()
        if PYPY:
            s.close()
        else:
            del s # Deliberately getting ResourceWarning under Py3
        try:
            os.close(w)
        except OSError:
            pass  # expected, because SocketAdapter already closed it
        else:
            raise AssertionError('os.close(%r) must not succeed' % w)
        fobj = FileObject(r, 'rb')
        self.assertEqual(fobj.read(), b'x')
        fobj.close()

    def test_del(self):
        self._test_del()

    def test_del_close(self):
        self._test_del(close=True)

    if FileObject is not FileObjectThread:

        def test_del_noclose(self):
            r, w = os.pipe()
            s = FileObject(w, 'wb', close=False)
            s.write(b'x')
            s.flush()
            if PYPY:
                s.close()
            else:
                del s
            os.close(w)
            self.assertEqual(FileObject(r).read(), b'x')

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


def writer(fobj, line):
    for character in line:
        fobj.write(character)
        fobj.flush()
    fobj.close()


try:
    from gevent.fileobject import SocketAdapter
except ImportError:
    pass
else:

    class TestSocketAdapter(greentest.TestCase):

        def _test_del(self, **kwargs):
            r, w = os.pipe()
            s = SocketAdapter(w)
            s.sendall(b'x')
            if PYPY:
                s.close()
            else:
                del s
            try:
                os.close(w)
            except OSError:
                pass  # expected, because SocketAdapter already closed it
            else:
                raise AssertionError('os.close(%r) must not succeed' % w)
            self.assertEqual(FileObject(r).read(), b'x')

        def test_del(self):
            self._test_del()

        def test_del_close(self):
            self._test_del(close=True)

        def test_del_noclose(self):
            r, w = os.pipe()
            s = SocketAdapter(w, close=False)
            s.sendall(b'x')
            del s
            os.close(w)
            self.assertEqual(FileObject(r).read(), b'x')


if __name__ == '__main__':
    greentest.main()
