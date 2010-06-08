from gevent import monkey; monkey.patch_socket()
import gevent
from gevent import http
import greentest
import os
from urllib2 import urlopen, HTTPError
import socket
import errno

# add test for "chunked POST input -> chunked output"


class BoundTestCase(greentest.TestCase):

    address = ('127.0.0.1', 0)

    def setUp(self):
        self.server = http.HTTPServer(self.address, self.handle)
        self.server.start()

    def tearDown(self):
        #self.print_netstat('before stop')
        timeout = gevent.Timeout.start_new(0.1)
        try:
            self.server.stop()
        finally:
            timeout.cancel()
        #self.print_netstat('after stop')
        self.check_refused()

    def print_netstat(self, comment=''):
        cmd ='sudo netstat -anp | grep %s' % self.server.server_port
        print cmd, ' # %s' % comment
        os.system(cmd)

    @property
    def url(self):
        return 'http://%s:%s' % (self.server.server_host, self.server.server_port)

    def connect(self):
        s = socket.socket()
        s.connect((self.server.server_host, self.server.server_port))
        return s

    def check_refused(self):
        try:
            self.connect()
        except socket.error, ex:
            if ex[0] != errno.ECONNREFUSED:
                raise
        except IOError, e:
            print 'WARNING: instead of ECONNREFUSED got IOError: %s' % e


class TestClientCloses(BoundTestCase):

    # this test is useless. currently there's no way to know that the client closed the connection,
    # because libevent calls close_cb callback after you've tried to push something to the client

    def handle(self, r):
        self.log.append('reply')
        gevent.sleep(0.1)
        r.send_reply(200, 'OK', 'hello world')
        # QQQ should I get an exception here because the connection is closed?
        self.log.append('reply_done')

    def test(self):
        self.log = ['hey']
        s = self.connect()
        s.sendall('GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\n')
        s.close()
        gevent.sleep(0.2)
        self.assertEqual(self.log, ['hey', 'reply', 'reply_done'])


class TestStop(BoundTestCase):

    # this triggers if connection_closed is not handled properly
    #p: http.c:1921: evhttp_send: Assertion `((&evcon->requests)->tqh_first) == req' failed.

    def reply(self, r):
        # at this point object that was wrapped by r no longer exists
        r.send_reply(200, 'OK', 'hello world')

    def handle(self, r):
        # gonna reply later, when the connection is closed by the client
        return gevent.spawn_later(0.01, self.reply, r)

    def test(self):
        s = self.connect()
        s.sendall('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        s.sendall('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        s.close()
        self.server.stop()
        gevent.sleep(0.02)
        # stopping what already stopped is OK
        self.server.stop()


class TestSendReply(BoundTestCase):

    def handle(self, r):
        r.send_reply(200, 'OK', 'hello world')

    def test(self):
        response = urlopen(self.url)
        assert response.code == 200, response
        assert response.msg == 'OK', response
        data = response.read()
        assert data == 'hello world', data

    def test_keepalive(self):
        s = self.connect()
        s.sendall('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        s.sendall('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')


class TestException(BoundTestCase):

    def handle(self, r):
        raise greentest.ExpectedException('TestException.handle')

    def test(self):
        try:
            urlopen(self.url)
        except HTTPError, e:
            assert e.code == 500, e
            assert e.msg == 'Internal Server Error', e


class TestSendReplyLater(BoundTestCase):

    def handle(self, r):
        gevent.sleep(0.01)
        r.send_reply(200, 'OK', 'hello world')

    def test(self):
        response = urlopen(self.url)
        #print 'connected to %s' % self.url
        assert response.code == 200, response
        assert response.msg == 'OK', response
        data = response.read()
        #print 'read data from %s' % self.url
        assert data == 'hello world', data

    def test_client_closes_10(self):
        s = self.connect()
        s.sendall('GET / HTTP/1.0\r\n\r\n')
        s.close()
        gevent.sleep(0.02)

    def test_client_closes_11(self):
        s = self.connect()
        s.sendall('GET / HTTP/1.1\r\n\r\n')
        s.close()
        gevent.sleep(0.02)


class TestDetach(BoundTestCase):

    def handle(self, r):
        input = r.input_buffer
        output = r.output_buffer
        assert r.input_buffer is input
        assert r.output_buffer is output
        assert input._obj
        assert output._obj
        r.detach()
        assert not input._obj
        assert not output._obj
        assert input.read() == ''
        assert output.read() == ''
        self.handled = True
        self.current.throw(Exception('test done'))

    def test(self):
        self.current = gevent.getcurrent()
        try:
            try:
                urlopen(self.url)
            except Exception, ex:
                assert str(ex) == 'test done', ex
        finally:
            self.current = None
        assert self.handled


# class TestSendReplyStartChunk(BoundTestCase):
#     spawn = True
#
#     def handle(self, r):
#         r.send_reply_start(200, 'OK')
#         gevent.sleep(0.2)
#         print 'handler sending chunk'
#         r.send_reply_chunk('hi')
#         print 'handler done'
#
#     def test(self):
#         response = urlopen(self.url)
#         print 'connected to %s' % self.url
#         assert response.code == 200, response
#         assert response.msg == 'OK', response
#         with gevent.Timeout(0.1, False):
#             data = response.read()
#             assert 'should not read anything', repr(data)
#         self.print_netstat('before response.close')
#         response.close()
#         self.print_netstat('after response.close')
#         print 123
#         gevent.sleep(0.5)
#         print 1234
#
#     def test_client_closes(self):
#         s = self.connect()
#         s.sendall('GET / HTTP/1.0\r\n\r\n')
#         gevent.sleep(0.1)
#         #self.print_netstat('before close')
#         s.close()
#         #self.print_netstat('after close')
#         gevent.sleep(0.5)


if __name__ == '__main__':
    greentest.main()

