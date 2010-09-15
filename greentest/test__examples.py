import sys
import os
import glob
from os.path import join, abspath, dirname, normpath, basename
import unittest
import urllib2
import time
import signal
import re
import gevent
from gevent import socket
import mysubprocess as subprocess

# Ignore tracebacks: KeyboardInterrupt

base_dir = normpath(join(dirname(abspath(__file__)), '..'))
glob_expression = join(base_dir, 'examples', '*.py')
examples = glob.glob(glob_expression)
simple_examples = []
examples_directory = dirname(examples[0])

for example in examples:
    if 'serve_forever' not in open(example).read():
        simple_examples.append(example)

print '\n'.join(examples)


def make_test(path):

    if ' ' in path:
        path = '"%s"' % path

    class TestExample(unittest.TestCase):

        def test(self):
            exe = sys.executable
            if ' ' in exe:
                exe = '"%s"' % exe
            cmd = '%s %s' % (exe, path)
            print >> sys.stderr, cmd
            res = os.system(cmd)
            assert not res, '%s failed with %s' % (path, res)

    TestExample.__name__ = 'TestExample_' + basename(path).split('.')[0]

    return TestExample


for example in simple_examples:
    test = make_test(example)
    globals()[test.__name__] = test
    print 'Added %s' % test.__name__
    del test


class BaseTestServer(unittest.TestCase):

    def setUp(self):
        self.process = subprocess.Popen([sys.executable, join(examples_directory, self.path)], cwd=examples_directory)
        time.sleep(1)

    def tearDown(self):
        self.assertEqual(self.process.poll(), None)
        self.process.interrupt()
        time.sleep(0.5)


class Test_httpserver(BaseTestServer):
    path = 'httpserver.py'
    URL = 'http://localhost:8088'
    not_found_message = '<h1>Not Found</h1>'

    def read(self, path='/'):
        url = self.URL + path
        try:
            response = urllib2.urlopen(url)
        except urllib2.HTTPError, response:
            pass
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


if hasattr(socket, 'ssl'):

    class Test_wsgiserver_ssl(Test_httpserver):
        path = 'wsgiserver_ssl.py'
        URL = 'https://localhost:8443'

else:

    class Test_wsgiserver_ssl(unittest.TestCase):
        path = 'wsgiserver_ssl.py'

        def setUp(self):
            self.process = subprocess.Popen([sys.executable, join(examples_directory, self.path)],
                                            cwd=examples_directory, stderr=subprocess.PIPE)
            time.sleep(1)

        def test(self):
            self.assertEqual(self.process.poll(), 1)
            stderr = self.process.stderr.read().strip()
            m = re.match('Traceback \(most recent call last\):.*?ImportError: .*?ssl.*', stderr, re.DOTALL)
            assert m is not None, repr(stderr)

        def tearDown(self):
            if self.process.poll() is None:
                try:
                    SIGINT = getattr(signal, 'SIGINT', None)
                    if SIGINT is not None:
                        os.kill(self.process.pid, SIGINT)
                        time.sleep(0.1)
                    self.assertEqual(self.process.poll(), 1)
                finally:
                    if self.process.poll() is None:
                        self.process.kill()


class Test_webpy(Test_httpserver):
    path = 'webpy.py'
    not_found_message = 'not found'

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert "Hello, world" in data, repr(data)

    def _test_long(self):
        start = time.time()
        status, data = self.read('/long')
        delay = time.time() - start
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
    path = 'echoserver.py'

    def test(self):
        def test_client(message):
            conn = socket.create_connection(('127.0.0.1', 6000)).makefile(bufsize=1)
            welcome = conn.readline()
            assert 'Welcome' in welcome, repr(welcome)
            conn.write(message)
            received = conn.read(len(message))
            self.assertEqual(received, message)
            conn._sock.settimeout(0.1)
            self.assertRaises(socket.timeout, conn.read, 1)
        client1 = gevent.spawn_link_exception(test_client, 'hello\r\n')
        client2 = gevent.spawn_link_exception(test_client, 'world\r\n')
        gevent.joinall([client1, client2])


class TestAllTested(unittest.TestCase):

    def test(self):
        tests = set()
        for klass in globals():
            if klass.startswith('Test'):
                path = getattr(globals()[klass], 'path', None)
                if path is not None:
                    tests.add(path)
        untested = set(examples) - set(simple_examples)
        untested = set(basename(path) for path in untested) - tests
        assert not untested, 'The following examples have not been tested: %s' % '\n'.join(untested)


if __name__ == '__main__':
    unittest.main()
