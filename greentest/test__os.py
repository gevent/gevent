from gevent import monkey; monkey.patch_all()

import os
from greentest import TestCase, main
from gevent import Greenlet, joinall
try:
    import fcntl
except ImportError:
    fcntl = None


class TestOS(TestCase):

    __timeout__ = 5

    def test_if_pipe_blocks(self):
        r, w = os.pipe()
        # set nbytes such that for sure it is > maximum pipe buffer
        nbytes = 1000000
        block = 'x' * 4096
        buf = buffer(block)
        # Lack of "nonlocal" keyword in Python 2.x:
        bytesread = [0]
        byteswritten = [0]
        def produce():
            while byteswritten[0] != nbytes:
                bytesleft = nbytes - byteswritten[0]
                byteswritten[0] += os.write(w, buf[:min(bytesleft, 4096)])
        def consume():
            while bytesread[0] != nbytes:
                bytesleft = nbytes - bytesread[0]
                bytesread[0] += len(os.read(r, min(bytesleft, 4096)))
        producer = Greenlet(produce)
        producer.start()
        consumer = Greenlet(consume)
        consumer.start_later(1)
        # If patching was not succesful, the producer will have filled
        # the pipe before the consumer starts, and would block the entire
        # process. Therefore the next line would never finish.
        joinall([producer, consumer])
        assert bytesread[0] == nbytes
        assert bytesread[0] == byteswritten[0]
 
    def test_fd_flags_restored(self):
        if fcntl is None:
            return
        r, w = os.pipe()
        flags = fcntl.fcntl(r, fcntl.F_GETFL, 0)
        assert not flags & os.O_NONBLOCK
        flags = fcntl.fcntl(w, fcntl.F_GETFL, 0)
        assert not flags & os.O_NONBLOCK
        os.write(w, 'foo')
        buf = os.read(r, 3)
        assert buf == 'foo'
        flags = fcntl.fcntl(r, fcntl.F_GETFL, 0)
        assert not flags & os.O_NONBLOCK
        flags = fcntl.fcntl(w, fcntl.F_GETFL, 0)
        assert not flags & os.O_NONBLOCK


if __name__ == '__main__':
    main()
