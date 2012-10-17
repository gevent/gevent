import os
import greentest
import gevent
from gevent.fileobject import FileObject, FileObjectThread

try:
    import fcntl
except ImportError:
    fcntl = None
    
try:
    import errno
except ImportError:
    errno = None


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
        
        def test_EBADF_from_read_with_fd_closed(self):
            if fcntl is None or errno is None:
                return
            
            r, w = os.pipe()
            rfile = FileObject(r, 'r', close=False)
            os.close(r)
            try:
                data = rfile.read()
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
            else:
                raise AssertionError('FileObject.read with closed fd must fail with EBADF')
            
            os.close(w)
            del rfile
            
            # Test when fd is closed during hub switch in read
            r, w = os.pipe()
            rfile = FileObject(r, 'r', close=False)
            # set nbytes such that for sure it is > maximum pipe buffer
            def close_fd(fd):
                os.close(fd)
            
            g = gevent.spawn(close_fd, fd=r)
            try:
                data = rfile.read()
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
            else:
                raise AssertionError('FileObject.read with closed fd must fail with EBADF')
            g.get()
            
                
        def test_fcntl_flags_preserved(self):
            if fcntl is None:
                return
            r, w = os.pipe()
            # duplicate fd's share the original's flags
            rdup = os.dup(r)
            wdup = os.dup(w)
            
            # Test that flags are preserved after read/write return
            rflags = fcntl.fcntl(r, fcntl.F_GETFL, 0)
            rdupflags = fcntl.fcntl(rdup, fcntl.F_GETFL, 0)
            self.assertEqual(rflags, rdupflags)
            
            wflags = fcntl.fcntl(w, fcntl.F_GETFL, 0)
            wdupflags = fcntl.fcntl(wdup, fcntl.F_GETFL, 0)
            self.assertEqual(wflags, wdupflags)
            
            rfile = FileObject(r, 'r', restore_flags=True)
            self.assertEqual(fcntl.fcntl(r, fcntl.F_GETFL, 0), rflags)
            wfile = FileObject(w, 'w', restore_flags=True)
            self.assertEqual(fcntl.fcntl(w, fcntl.F_GETFL, 0), wflags)
            
            wfile.write("foo")
            wfile.flush()
            self.assertEqual(fcntl.fcntl(w, fcntl.F_GETFL, 0), wflags)
            data = rfile.read(3)
            self.assertEqual(data, "foo")
            self.assertEqual(fcntl.fcntl(r, fcntl.F_GETFL, 0), rflags)
            
            # Test that write-end flags are preserved during hub switch in write
            # set nbytes such that for sure it is > maximum pipe buffer
            nbytes = 1000000
            def consume(f):
                wflags_at_start = fcntl.fcntl(w, fcntl.F_GETFL, 0)
                data = f.read(nbytes)
                self.assertEqual(len(data), nbytes)
                self.assertEqual(wflags_at_start, wflags)
                self.assertEqual(fcntl.fcntl(w, fcntl.F_GETFL, 0), wflags)
                self.assertEqual(fcntl.fcntl(r, fcntl.F_GETFL, 0), rflags)
            
            g = gevent.spawn(consume, f=rfile)
            wfile.write("d" * nbytes)
            wfile.flush()
            g.get()
            del g
            
            # Test that read-end flags are preserved during hub switch in read
            def produce(f):
                rflags_at_start = fcntl.fcntl(r, fcntl.F_GETFL, 0)
                f.write("d" * nbytes)
                f.flush()
                self.assertEqual(rflags_at_start, rflags)
                self.assertEqual(fcntl.fcntl(r, fcntl.F_GETFL, 0), rflags)
                self.assertEqual(fcntl.fcntl(w, fcntl.F_GETFL, 0), wflags)
            
            g = gevent.spawn(produce, f=wfile)
            data = rfile.read(nbytes)
            self.assertEqual(len(data), nbytes)
            g.get()
            del g
            
            # Test that flags are preserved after destruction of FileObjects
            del rfile
            self.assertEqual(fcntl.fcntl(rdup, fcntl.F_GETFL, 0), rdupflags)
            del wfile
            self.assertEqual(fcntl.fcntl(wdup, fcntl.F_GETFL, 0), wdupflags)
            

    def test_newlines(self):
        r, w = os.pipe()
        lines = ['line1\n', 'line2\r', 'line3\r\n', 'line4\r\nline5', '\nline6']
        g = gevent.spawn(writer, FileObject(w, 'wb'), lines)
        try:
            result = FileObject(r, 'rU').read()
            self.assertEqual('line1\nline2\nline3\nline4\nline5\nline6', result)
        finally:
            g.kill()
    
    def test_newlines_only_in_small_read_chunks(self):
        r, w = os.pipe()
        r = FileObject(r, "rbU", bufsize=1)
        w = FileObject(w, "wb")
      
        def read(r):
          all_received_data = ""
          
          while True:
            data = r.read(1)
            if not data:
              break
            all_received_data += data
            
          return all_received_data
        
        reader_greenlet = gevent.spawn(read, r)
        
        data = "\n\r" * 2
        w.write(data)
        w.close()
        
        all_received_data = reader_greenlet.get()
        
        total_bytes_read = len(all_received_data)
        total_bytes_expected = (len(data)/2) + data.startswith("\n")
        
        self.assertEqual(total_bytes_read, total_bytes_expected,
                         msg="read %d bytes, expected=%d bytes" % (
                            total_bytes_read, total_bytes_expected))
        
        self.assertTrue(all((c == "\n") for c in all_received_data),
                        msg=("Expected only newlines, but got a combination of "
                             "these chars: %r") % (set(all_received_data),))


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
