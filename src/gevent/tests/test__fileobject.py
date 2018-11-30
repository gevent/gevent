from __future__ import print_function
import os
import sys
import tempfile
import gc
import unittest

import gevent
from gevent import fileobject

import gevent.testing as greentest
from gevent.testing.sysinfo import PY3
from gevent.testing.flaky import reraiseFlakyTestRaceConditionLibuv
from gevent.testing.skipping import skipOnLibuvOnCIOnPyPy


try:
    ResourceWarning
except NameError:
    class ResourceWarning(Warning):
        "Python 2 fallback"


def writer(fobj, line):
    for character in line:
        fobj.write(character)
        fobj.flush()
    fobj.close()


def close_fd_quietly(fd):
    try:
        os.close(fd)
    except (IOError, OSError):
        pass

class TestFileObjectBlock(greentest.TestCase):

    def _getTargetClass(self):
        return fileobject.FileObjectBlock

    def _makeOne(self, *args, **kwargs):
        return self._getTargetClass()(*args, **kwargs)

    def _test_del(self, **kwargs):
        r, w = os.pipe()
        self.addCleanup(close_fd_quietly, r)
        self.addCleanup(close_fd_quietly, w)

        self._do_test_del((r, w), **kwargs)

    def _do_test_del(self, pipe, **kwargs):
        r, w = pipe
        s = self._makeOne(w, 'wb', **kwargs)
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

        with self._makeOne(r, 'rb') as fobj:
            self.assertEqual(fobj.read(), b'x')

    def test_del(self):
        # Close should be true by default
        self._test_del()

    def test_del_close(self):
        self._test_del(close=True)

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
                f = self._makeOne(f_raw, 'rb', close=False)
            except ValueError:
                # libuv on Travis can raise EPERM
                # from FileObjectPosix. I can't produce it on mac os locally,
                # don't know what the issue is. This started happening on Jan 19,
                # in the branch that caused all watchers to be explicitly closed.
                # That shouldn't have any effect on io watchers, though, which were
                # already being explicitly closed.
                reraiseFlakyTestRaceConditionLibuv()

            if PY3 or hasattr(f, 'seekable'):
                # On Python 3, all objects should have seekable.
                # On Python 2, only our custom objects do.
                self.assertTrue(f.seekable())
            f.seek(15)
            self.assertEqual(15, f.tell())

            # Note that a duplicate close() of the underlying
            # file descriptor can look like an OSError from this line
            # as we exit the with block
            fileobj_data = f.read(1024)

        self.assertEqual(native_data, s)
        self.assertEqual(native_data, fileobj_data)

    def test_close_pipe(self):
        # Issue #190, 203
        r, w = os.pipe()
        x = self._makeOne(r)
        y = self._makeOne(w, 'w')
        x.close()
        y.close()


class ConcurrentFileObjectMixin(object):
    # Additional tests for fileobjects that cooperate
    # and we have full control of the implementation

    def test_read1(self):
        # Issue #840
        r, w = os.pipe()
        x = self._makeOne(r)
        y = self._makeOne(w, 'w')
        self._close_on_teardown(x)
        self._close_on_teardown(y)
        self.assertTrue(hasattr(x, 'read1'))

    def test_bufsize_0(self):
        # Issue #840
        r, w = os.pipe()
        x = self._makeOne(r, 'rb', bufsize=0)
        y = self._makeOne(w, 'wb', bufsize=0)
        self._close_on_teardown(x)
        self._close_on_teardown(y)
        y.write(b'a')
        b = x.read(1)
        self.assertEqual(b, b'a')

        y.writelines([b'2'])
        b = x.read(1)
        self.assertEqual(b, b'2')

    def test_newlines(self):
        import warnings
        r, w = os.pipe()
        lines = [b'line1\n', b'line2\r', b'line3\r\n', b'line4\r\nline5', b'\nline6']
        g = gevent.spawn(writer, self._makeOne(w, 'wb'), lines)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                # U is deprecated in Python 3, shows up on FileObjectThread
                fobj = self._makeOne(r, 'rU')
            result = fobj.read()
            fobj.close()
            self.assertEqual('line1\nline2\nline3\nline4\nline5\nline6', result)
        finally:
            g.kill()


class TestFileObjectThread(ConcurrentFileObjectMixin,
                           TestFileObjectBlock):

    def _getTargetClass(self):
        return fileobject.FileObjectThread

    # FileObjectThread uses os.fdopen() when passed a file-descriptor,
    # which returns an object with a destructor that can't be
    # bypassed, so we can't even create one that way
    def test_del_noclose(self):
        with self.assertRaisesRegex(TypeError,
                                    'FileObjectThread does not support close=False on an fd.'):
            self._test_del(close=False)

    # We don't test this with FileObjectThread. Sometimes the
    # visibility of the 'close' operation, which happens in a
    # background thread, doesn't make it to the foreground
    # thread in a timely fashion, leading to 'os.close(4) must
    # not succeed' in test_del_close. We have the same thing
    # with flushing and closing in test_newlines. Both of
    # these are most commonly (only?) observed on Py27/64-bit.
    # They also appear on 64-bit 3.6 with libuv

    def test_del(self):
        raise unittest.SkipTest("Race conditions")

    def test_del_close(self):
        raise unittest.SkipTest("Race conditions")


@unittest.skipUnless(
    hasattr(fileobject, 'FileObjectPosix'),
    "Needs FileObjectPosix"
)
class TestFileObjectPosix(ConcurrentFileObjectMixin,
                          TestFileObjectBlock):

    def _getTargetClass(self):
        return fileobject.FileObjectPosix

    def test_seek_raises_ioerror(self):
        # https://github.com/gevent/gevent/issues/1323

        # Get a non-seekable file descriptor
        r, w = os.pipe()

        self.addCleanup(close_fd_quietly, r)
        self.addCleanup(close_fd_quietly, w)

        with self.assertRaises(OSError) as ctx:
            os.lseek(r, 0, os.SEEK_SET)
        os_ex = ctx.exception

        with self.assertRaises(IOError) as ctx:
            f = self._makeOne(r, 'r', close=False)
            # Seek directly using the underlying GreenFileDescriptorIO;
            # the buffer may do different things, depending
            # on the version of Python (especially 3.7+)
            f.fileio.seek(0)
        io_ex = ctx.exception

        self.assertEqual(io_ex.errno, os_ex.errno)
        self.assertEqual(io_ex.strerror, os_ex.strerror)
        self.assertEqual(io_ex.args, os_ex.args)
        self.assertEqual(str(io_ex), str(os_ex))


class TestTextMode(unittest.TestCase):

    def test_default_mode_writes_linesep(self):
        # See https://github.com/gevent/gevent/issues/1282
        # libuv 1.x interferes with the default line mode on
        # Windows.
        # First, make sure we initialize gevent
        gevent.get_hub()

        fileno, path = tempfile.mkstemp('.gevent.test__fileobject.test_default')
        self.addCleanup(os.remove, path)

        os.close(fileno)

        with open(path, "w") as f:
            f.write("\n")

        with open(path, "rb") as f:
            data = f.read()

        self.assertEqual(data, os.linesep.encode('ascii'))



if __name__ == '__main__':
    sys.argv.append('-v')
    greentest.main()
