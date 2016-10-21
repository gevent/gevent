import sys
import _six as six
from os import pipe
import gevent
from gevent import os
from greentest import TestCase, main
from gevent import Greenlet, joinall


class TestOS_tp(TestCase):

    __timeout__ = 5

    def pipe(self):
        return pipe()

    def read(self, *args):
        return os.tp_read(*args)

    def write(self, *args):
        return os.tp_write(*args)

    def _test_if_pipe_blocks(self, buffer_class):
        r, w = self.pipe()
        # set nbytes such that for sure it is > maximum pipe buffer
        nbytes = 1000000
        block = b'x' * 4096
        buf = buffer_class(block)
        # Lack of "nonlocal" keyword in Python 2.x:
        bytesread = [0]
        byteswritten = [0]

        def produce():
            while byteswritten[0] != nbytes:
                bytesleft = nbytes - byteswritten[0]
                byteswritten[0] += self.write(w, buf[:min(bytesleft, 4096)])

        def consume():
            while bytesread[0] != nbytes:
                bytesleft = nbytes - bytesread[0]
                bytesread[0] += len(self.read(r, min(bytesleft, 4096)))

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

    if sys.version_info[0] < 3:

        def test_if_pipe_blocks_buffer(self):
            self._test_if_pipe_blocks(six.builtins.buffer)

    if sys.version_info[:2] >= (2, 7):

        def test_if_pipe_blocks_memoryview(self):
            self._test_if_pipe_blocks(six.builtins.memoryview)


if hasattr(os, 'make_nonblocking'):

    class TestOS_nb(TestOS_tp):

        def pipe(self):
            r, w = pipe()
            os.make_nonblocking(r)
            os.make_nonblocking(w)
            return r, w

        def read(self, *args):
            return os.nb_read(*args)

        def write(self, *args):
            return os.nb_write(*args)


if hasattr(os, 'fork_and_watch'):

    class TestForkAndWatch(TestCase):

        __timeout__ = 5

        def test_waitpid_all(self):
            # Cover this specific case.
            pid = os.fork_and_watch()
            if pid:
                os.waitpid(-1, 0)
                # Can't assert on what the pid actually was,
                # our testrunner may have spawned multiple children.
                os._reap_children(0) # make the leakchecker happy
            else:
                gevent.sleep(2)
                os._exit(0)

        def test_waitpid_wrong_neg(self):
            self.assertRaises(OSError, os.waitpid, -2, 0)

        def test_waitpid_wrong_pos(self):
            self.assertRaises(OSError, os.waitpid, 1, 0)

if __name__ == '__main__':
    main()
