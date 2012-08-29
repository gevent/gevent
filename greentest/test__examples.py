from __future__ import with_statement
import sys
import os
import glob
from os.path import join, abspath, dirname, normpath, basename
import unittest
if sys.version_info[0] == 3:
    from urllib import request as urllib2
else:
    import urllib2
from urlparse import urlparse
from time import time
import gevent
from gevent import socket
from gevent import subprocess
from gevent.server import DatagramServer, StreamServer

# Ignore tracebacks: KeyboardInterrupt

examples_directory = normpath(join(dirname(abspath(__file__)), '..', 'examples'))
examples = [basename(x) for x in glob.glob(examples_directory + '/*.py')]
simple_examples = []
default_time_range = (0.0, 10.0)


for example in examples:
    if 'serve_forever' not in open(join(examples_directory, example)).read():
        simple_examples.append(example)


class TestCase(unittest.TestCase):

    def run_script(self, *args, **kwargs):
        cmd = [sys.executable, join(examples_directory, self.path)] + list(args)
        start = time()
        subprocess.check_call(cmd, **kwargs)
        took = time() - start
        min_time, max_time = getattr(self, 'time_range', default_time_range)
        assert took >= min_time, '%s exited too quickly %s %s' % (self.path, took, min_time)
        assert took <= max_time, '%s takes way too long %s %s' % (self.path, took, max_time)


def make_test(path):

    if sys.platform == 'win32' and os.path.basename(path) in ('geventsendfile.py', 'processes.py'):
        print 'Ignoring', path
        return

    if ' ' in path:
        path = '"%s"' % path

    class Test(TestCase):

        def test(self):
            self.run_script()

    Test.__name__ = 'Test_' + basename(path).split('.')[0]
    assert Test.__name__ not in globals(), Test.__name__
    Test.path = path
    return Test


def kill(popen):
    try:
        popen.kill()
    except OSError, ex:
        if ex.errno == 3:  # No such process
            return
        if ex.errno == 13:  # Permission denied (translated from windows error 5: "Access is denied")
            return
        raise
    popen.wait()


class BaseTestServer(unittest.TestCase):
    args = []

    stderr = None

    def get_address(self):
        parsed = urlparse(self.URL)
        return parsed.hostname, parsed.port

    def get_sock_type(self):
        parsed = urlparse(self.URL)
        if parsed.scheme.lower() == 'udp':
            return socket.SOCK_DGRAM
        return socket.SOCK_STREAM

    def assert_refused(self):
        if self.get_sock_type() == socket.SOCK_DGRAM:
            return
        try:
            self.connect()
        except socket.error, ex:
            if 'refused' not in str(ex):
                raise
        else:
            raise AssertionError('Connection to %s succeeds before starting the server' % self.URL)

    def connect(self):
        sock = socket.socket(type=self.get_sock_type())
        sock.connect(self.get_address())
        return sock

    def wait_start(self, timeout):
        end = time() + timeout
        while time() <= end:
            if self.process.poll() is not None:
                raise AssertionError('Process died')
            try:
                self.connect()
            except socket.error:
                gevent.sleep(0.01)
            else:
                return
        else:
            raise AssertionError('Failed to start')

    def setUp(self):
        self.assert_refused()
        self.process = subprocess.Popen([sys.executable, join(examples_directory, self.path)] + self.args,
                                        cwd=examples_directory, stderr=self.stderr)
        try:
            self.wait_start(1)
        except:
            kill(self.process)
            raise
        assert self.process.poll() is None, self.process

    def tearDown(self):
        kill(self.process)


class Test_httpserver(BaseTestServer):
    URL = 'http://localhost:8088'
    not_found_message = '<h1>Not Found</h1>'

    def read(self, path='/'):
        url = self.URL + path
        try:
            response = urllib2.urlopen(url)
        except urllib2.HTTPError:
            response = sys.exc_info()[1]
        return '%s %s' % (response.code, response.msg), response.read()

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, "<b>hello world</b>")

    def _test_not_found(self):
        status, data = self.read('/xxx')
        self.assertEqual(status, '404 Not Found')
        self.assertEqual(data, self.not_found_message)

    def test(self):
        # running all the test methods now so that we don't set up a server more than once
        for method in dir(self):
            if method.startswith('_test'):
                function = getattr(self, method)
                if callable(function):
                    function()


class Test_wsgiserver(Test_httpserver):
    path = 'wsgiserver.py'


class Test_wsgiserver_ssl(Test_httpserver):
    path = 'wsgiserver_ssl.py'
    URL = 'https://localhost:8443'

    def connect(self):
        sock = super(Test_wsgiserver_ssl, self).connect()
        from gevent import ssl
        return ssl.wrap_socket(sock)


class Test_webpy(Test_httpserver):
    path = 'webpy.py'
    not_found_message = 'not found'

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert "Hello, world" in data, repr(data)

    def _test_long(self):
        start = time()
        status, data = self.read('/long')
        delay = time() - start
        assert 10 - 0.1 < delay < 10 + 0.1, delay
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, 'Hello, 10 seconds later')


class Test_webproxy(Test_httpserver):
    path = 'webproxy.py'

    def test(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert "gevent example" in data, repr(data)
        status, data = self.read('/http://www.google.com')
        self.assertEqual(status, '200 OK')
        assert 'google' in data.lower(), repr(data)


class Test_echoserver(BaseTestServer):
    URL = 'tcp://127.0.0.1:6000'
    path = 'echoserver.py'

    def test(self):
        def test_client(message):
            conn = self.connect().makefile(bufsize=1)
            welcome = conn.readline()
            assert 'Welcome' in welcome, repr(welcome)
            conn.write(message)
            received = conn.read(len(message))
            self.assertEqual(received, message)
            conn._sock.settimeout(0.1)
            self.assertRaises(socket.timeout, conn.read, 1)
        client1 = gevent.spawn(test_client, 'hello\r\n')
        client2 = gevent.spawn(test_client, 'world\r\n')
        gevent.joinall([client1, client2], raise_error=True)


class Test_udp_client(TestCase):

    path = 'udp_client.py'

    def test(self):
        log = []
        def handle(message, address):
            log.append(message)
            server.sendto('reply-from-server', address)
        server = DatagramServer('127.0.0.1:9000', handle)
        server.start()
        try:
            self.run_script('Test_udp_client')
        finally:
            server.close()
        self.assertEqual(log, ['Test_udp_client'])


class Test_udp_server(BaseTestServer):
    path = 'udp_server.py'
    URL = 'udp://localhost:9000'

    def test(self):
        gevent.sleep(0.3)
        sock = self.connect()
        sock.send('Test_udp_server')
        data, address = sock.recvfrom(8192)
        self.assertEqual(data, 'Received 15 bytes')


class Test_portforwarder(BaseTestServer):
    path = 'portforwarder.py'
    args = ['127.0.0.1:10011', '127.0.0.1:10012']
    URL = 'tcp://' + args[0]

    def test(self):
        log = []

        def handle(socket, address):
            while True:
                data = socket.recv(1024)
                if not data:
                    break
                log.append(data)

        server = StreamServer(self.args[1], handle)
        server.start()
        try:
            conn = socket.create_connection(self.get_address())
            # make sure the connection is accepted at app level rather than at OS level
            # before sending a signal
            conn.sendall('msg1')
            gevent.sleep(0.1)
            self.process.send_signal(15)
            # now let's make sure the signal was received
            gevent.sleep(0.1)
            conn.sendall('msg2')
            conn.close()
        finally:
            server.close()

        with gevent.Timeout(0.1):
            self.process.wait()

        self.assertEqual(['msg1', 'msg2'], log)


tests = set()
for klass in globals().keys():
    if klass.startswith('Test'):
        path = getattr(globals()[klass], 'path', None)
        if path is not None:
            tests.add(path)


for example in simple_examples:
    if example in tests:
        continue
    test = make_test(example)
    if test is not None:
        globals()[test.__name__] = test
        print ('Added %s' % test.__name__)
    del test


Test_psycopg2_pool.time_range = (2.0, 2.5)
Test_threadpool.time_range = (2.0, 3.0)


class TestAllTested(unittest.TestCase):

    def test(self):
        untested = set(examples) - set(simple_examples)
        untested = set(basename(path) for path in untested) - tests
        if untested:
            raise AssertionError('The following examples have not been tested: %s\n - %s' % (len(untested), '\n - '.join(untested)))


del Test_httpserver


if __name__ == '__main__':
    unittest.main()
