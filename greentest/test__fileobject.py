import os
import greentest
import gevent
from gevent.fileobject import FileObject, FileObjectThread


class Test(greentest.TestCase):

    def _test_del(self, **kwargs):
        r, w = os.pipe()
        s = FileObject(w, 'wb')
        s.write('x')
        s.flush()
        del s
        try:
            os.close(w)
        except OSError:
            pass  # expected, because SocketAdapter already closed it
        else:
            raise AssertionError('os.close(%r) must not succeed' % w)
        self.assertEqual(FileObject(r).read(), 'x')

    def test_del(self):
        self._test_del()

    def test_del_close(self):
        self._test_del(close=True)

    if FileObject is not FileObjectThread:

        def test_del_noclose(self):
            r, w = os.pipe()
            s = FileObject(w, 'wb', close=False)
            s.write('x')
            s.flush()
            del s
            os.close(w)
            self.assertEqual(FileObject(r).read(), 'x')

    def test_newlines(self):
        r, w = os.pipe()
        lines = ['line1\n', 'line2\r', 'line3\r\n', 'line4\r\nline5', '\nline6']
        g = gevent.spawn(writer, FileObject(w, 'wb'), lines)
        try:
            result = FileObject(r, 'rU').read()
            self.assertEqual('line1\nline2\nline3\nline4\nline5\nline6', result)
        finally:
            g.kill()


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
            s.sendall('x')
            del s
            try:
                os.close(w)
            except OSError:
                pass  # expected, because SocketAdapter already closed it
            else:
                raise AssertionError('os.close(%r) must not succeed' % w)
            self.assertEqual(FileObject(r).read(), 'x')

        def test_del(self):
            self._test_del()

        def test_del_close(self):
            self._test_del(close=True)

        def test_del_noclose(self):
            r, w = os.pipe()
            s = SocketAdapter(w, close=False)
            s.sendall('x')
            del s
            os.close(w)
            self.assertEqual(FileObject(r).read(), 'x')


if __name__ == '__main__':
    greentest.main()
