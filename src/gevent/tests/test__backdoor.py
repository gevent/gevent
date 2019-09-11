from __future__ import print_function
from __future__ import absolute_import

import gevent
from gevent import socket
from gevent import backdoor

import gevent.testing as greentest
from gevent.testing.params import DEFAULT_BIND_ADDR_TUPLE
from gevent.testing.params import DEFAULT_CONNECT

def read_until(conn, postfix):
    read = b''
    assert isinstance(postfix, bytes)

    while not read.endswith(postfix):
        result = conn.recv(1)
        if not result:
            raise AssertionError('Connection ended before %r. Data read:\n%r' % (postfix, read))
        read += result

    return read if isinstance(read, str) else read.decode('utf-8')

def readline(conn):
    with conn.makefile() as f:
        return f.readline()

class WorkerGreenlet(gevent.Greenlet):

    spawning_stack_limit = 2

class Test(greentest.TestCase):

    __timeout__ = 10

    _server = None

    def tearDown(self):
        if self._server is not None:
            self._server.stop()
            self.close_on_teardown.remove(self._server.stop)
        self._server = None
        gevent.sleep() # let spawned greenlets die
        super(Test, self).tearDown()

    def _make_server(self, *args, **kwargs):
        assert self._server is None
        self._server = backdoor.BackdoorServer(DEFAULT_BIND_ADDR_TUPLE, *args, **kwargs)
        self._close_on_teardown(self._server.stop)
        self._server.start()

    def _create_connection(self):
        conn = socket.socket()
        self._close_on_teardown(conn)
        conn.connect((DEFAULT_CONNECT, self._server.server_port))
        banner = self._wait_for_prompt(conn)
        return conn, banner

    def _wait_for_prompt(self, conn):
        return read_until(conn, b'>>> ')

    def _make_server_and_connect(self, *args, **kwargs):
        self._make_server(*args, **kwargs)
        return self._create_connection()

    def _close(self, conn, cmd=b'quit()\r\n)'):
        conn.sendall(cmd)
        line = readline(conn)
        self.assertEqual(line, '')
        conn.close()
        self.close_on_teardown.remove(conn)

    @greentest.skipOnLibuvOnTravisOnCPython27(
        "segfaults; "
        "See https://github.com/gevent/gevent/pull/1156")
    def test_multi(self):
        self._make_server()

        def connect():
            conn, _ = self._create_connection()
            conn.sendall(b'2+2\r\n')
            line = readline(conn)
            self.assertEqual(line.strip(), '4', repr(line))
            self._close(conn)

        jobs = [WorkerGreenlet.spawn(connect) for _ in range(10)]
        try:
            done = gevent.joinall(jobs, raise_error=True)
        finally:
            gevent.joinall(jobs, raise_error=False)

        self.assertEqual(len(done), len(jobs), done)

    def test_quit(self):
        conn, _ = self._make_server_and_connect()
        self._close(conn)

    def test_sys_exit(self):
        conn, _ = self._make_server_and_connect()
        self._close(conn, b'import sys; sys.exit(0)\r\n')

    def test_banner(self):
        expected_banner = "Welcome stranger!" # native string
        conn, banner = self._make_server_and_connect(banner=expected_banner)
        self.assertEqual(banner[:len(expected_banner)], expected_banner, banner)

        self._close(conn)

    def test_builtins(self):
        conn, _ = self._make_server_and_connect()
        conn.sendall(b'locals()["__builtins__"]\r\n')
        response = read_until(conn, b'>>> ')
        self.assertLess(
            len(response), 300,
            msg="locals() unusable: %s..." % response)

        self._close(conn)

    def test_switch_exc(self):
        from gevent.queue import Queue, Empty

        def bad():
            q = Queue()
            print('switching out, then throwing in')
            try:
                q.get(block=True, timeout=0.1)
            except Empty:
                print("Got Empty")
            print('switching out')
            gevent.sleep(0.1)
            print('switched in')

        conn, _ = self._make_server_and_connect(locals={'bad': bad})
        conn.sendall(b'bad()\r\n')
        response = self._wait_for_prompt(conn)
        response = response.replace('\r\n', '\n')
        self.assertEqual(
            'switching out, then throwing in\nGot Empty\nswitching out\nswitched in\n>>> ',
            response)

        self._close(conn)

if __name__ == '__main__':
    greentest.main()
