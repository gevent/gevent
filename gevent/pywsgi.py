# @author Bob Ippolito
#
# Copyright (c) 2005-2006, Bob Ippolito
# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2009-2010, gevent contributors
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import errno
import sys
import time
import traceback

from urllib import unquote
from gevent import socket
import BaseHTTPServer
import gevent
from gevent.server import StreamServer


MAX_REQUEST_LINE = 8192


# Weekday and month names for HTTP date/time formatting; always English!
_weekdayname = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_monthname = [None, # Dummy so we can use 1-based month numbers
              "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


_INTERNAL_ERROR_STATUS = '500 Internal Server Error'
_INTERNAL_ERROR_RESPONSE = """HTTP/1.0 500 Internal Server Error
Connection: close
Content-type: text/plain
Content-length: 21

Internal Server Error""".replace('\n', '\r\n')


def format_date_time(timestamp):
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
    return "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (_weekdayname[wd], day, _monthname[month], year, hh, mm, ss)


class Input(object):

    def __init__(self, rfile, content_length, wfile=None, wfile_line=None, chunked_input=False):
        self.rfile = rfile
        if content_length is not None:
            content_length = int(content_length)
        self.content_length = content_length

        self.wfile = wfile
        self.wfile_line = wfile_line

        self.position = 0
        self.chunked_input = chunked_input
        self.chunk_length = -1

    def _do_read(self, reader, length=None):
        if self.wfile is not None:
            ## 100 Continue
            self.wfile.write(self.wfile_line)
            self.wfile = None
            self.wfile_line = None

        if length is None and self.content_length is not None:
            length = self.content_length - self.position
        if length and length > self.content_length - self.position:
            length = self.content_length - self.position
        if not length:
            return ''
        read = reader(length)
        self.position += len(read)
        return read

    def _chunked_read(self, rfile, length=None):
        if self.wfile is not None:
            ## 100 Continue
            self.wfile.write(self.wfile_line)
            self.wfile = None
            self.wfile_line = None

        response = []
        if length is None:
            if self.chunk_length > self.position:
                response.append(rfile.read(self.chunk_length - self.position))
            while self.chunk_length != 0:
                self.chunk_length = int(rfile.readline(), 16)
                response.append(rfile.read(self.chunk_length))
                rfile.readline()
        else:
            while length > 0 and self.chunk_length != 0:
                if self.chunk_length > self.position:
                    response.append(rfile.read(
                            min(self.chunk_length - self.position, length)))
                    length -= len(response[-1])
                    self.position += len(response[-1])
                    if self.chunk_length == self.position:
                        rfile.readline()
                else:
                    self.chunk_length = int(rfile.readline(), 16)
                    self.position = 0
        return ''.join(response)

    def read(self, length=None):
        if self.chunked_input:
            return self._chunked_read(self.rfile, length)
        return self._do_read(self.rfile.read, length)

    def readline(self, size=None):
        return self._do_read(self.rfile.readline)

    def readlines(self, hint=None):
        return self.__iter__()

    def __iter__(self):
        while True:
            line = self.readline()
            if not line:
                break
            yield line


class HttpProtocol(BaseHTTPServer.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def handle_one_request(self):
        if self.rfile.closed:
            self.close_connection = 1
            return

        try:
            self.raw_requestline = self.rfile.readline(MAX_REQUEST_LINE)
            if len(self.raw_requestline) == MAX_REQUEST_LINE:
                self.wfile.write(
                    "HTTP/1.0 414 Request URI Too Long\r\nConnection: close\r\nContent-length: 0\r\n\r\n")
                self.close_connection = 1
                return
        except socket.error, e:
            if e[0] != errno.EBADF and e[0] != errno.ECONNRESET:
                raise
            self.raw_requestline = ''

        if not self.raw_requestline:
            self.close_connection = 1
            return

        if not self.parse_request():
            return

        self.environ = self.get_environ()
        self.application = self.server.application
        try:
            self.handle_one_response()
        except socket.error, e:
            # Broken pipe, connection reset by peer
            if e[0] in (errno.EPIPE, errno.ECONNRESET):
                pass
            else:
                raise

    def write(self, data):
        towrite = []
        if not self.status:
            raise AssertionError("write() before start_response()")
        elif not self.headers_sent:
            self.headers_sent = True
            towrite.append('%s %s\r\n' % (self.protocol_version, self.status))
            for header in self.response_headers:
                towrite.append('%s: %s\r\n' % header)

            # send Date header?
            if 'Date' not in self.response_headers_list:
                towrite.append('Date: %s\r\n' % (format_date_time(time.time()),))
            if self.request_version == 'HTTP/1.0':
                towrite.append('Connection: close\r\n')
                self.close_connection = 1
            elif 'Content-Length' not in self.response_headers_list:
                self.response_use_chunked = True
                towrite.append('Transfer-Encoding: chunked\r\n')
            towrite.append('\r\n')

        if self.response_use_chunked:
            ## Write the chunked encoding
            towrite.append("%x\r\n%s\r\n" % (len(data), data))
        else:
            towrite.append(data)

        self.wfile.writelines(towrite)
        self.response_length += sum(map(len, towrite))

    def start_response(self, status, headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                # Avoid dangling circular ref
                exc_info = None
        self.status = status
        self.response_headers = [('-'.join([x.capitalize() for x in key.split('-')]), value) for key, value in headers]
        self.response_headers_list = [x[0] for x in self.response_headers]
        def safe_write(d):
            if len(d):
                self.write(d)
        return safe_write

    def handle_one_response(self):
        start = time.time()
        self.status = None
        self.headers_sent = False

        result = None
        self.response_use_chunked = False
        self.response_length = 0

        try:
            try:
                result = self.application(self.environ, self.start_response)
                if not self.headers_sent and hasattr(result, '__len__') and 'Content-Length' not in self.response_headers_list:
                    self.response_headers.append(('Content-Length', str(sum(map(len, result)))))
                    self.response_headers_list.append('Content-Length')
                for data in result:
                    if data:
                        self.write(data)
                if not self.headers_sent or self.response_use_chunked:
                    self.write('')
            except Exception:
                self.status = _INTERNAL_ERROR_STATUS
                self.close_connection = 1
                self.server.log_message(traceback.format_exc())
                if not self.response_length:
                    self.wfile.write(_INTERNAL_ERROR_RESPONSE)
        finally:
            if hasattr(result, 'close'):
                result.close()
            if self.wsgi_input.position < self.environ.get('CONTENT_LENGTH', 0):
                ## Read and discard body
                self.wsgi_input.read()
            finish = time.time()

            self.server.log_message('%s - - [%s] "%s" %s %s %.6f' % (
                self.client_address[0],
                self.log_date_time_string(),
                self.requestline,
                self.status.split()[0],
                self.response_length,
                finish - start))

    def get_environ(self):
        env = self.server.get_environ()
        env['REQUEST_METHOD'] = self.command
        env['SCRIPT_NAME'] = ''

        if '?' in self.path:
            path, query = self.path.split('?', 1)
        else:
            path, query = self.path, ''
        env['PATH_INFO'] = unquote(path)
        env['QUERY_STRING'] = query

        if self.headers.typeheader is None:
            env['CONTENT_TYPE'] = self.headers.type
        else:
            env['CONTENT_TYPE'] = self.headers.typeheader

        length = self.headers.getheader('content-length')
        if length:
            env['CONTENT_LENGTH'] = length
        env['SERVER_PROTOCOL'] = 'HTTP/1.0'

        host, port = self.request.getsockname()
        env['SERVER_NAME'] = host
        env['SERVER_PORT'] = str(port)
        env['REMOTE_ADDR'] = self.client_address[0]
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'

        for h in self.headers.headers:
            k, v = h.split(':', 1)
            k = k.replace('-', '_').upper()
            v = v.strip()
            if k in env:
                continue
            envk = 'HTTP_' + k
            if envk in env:
                env[envk] += ',' + v
            else:
                env[envk] = v

        if env.get('HTTP_EXPECT') == '100-continue':
            wfile = self.wfile
            wfile_line = 'HTTP/1.1 100 Continue\r\n\r\n'
        else:
            wfile = None
            wfile_line = None
        chunked = env.get('HTTP_TRANSFER_ENCODING', '').lower() == 'chunked'
        self.wsgi_input = Input(self.rfile, length, wfile=wfile, wfile_line=wfile_line, chunked_input=chunked)
        env['wsgi.input'] = self.wsgi_input
        return env

    def finish(self):
        BaseHTTPServer.BaseHTTPRequestHandler.finish(self)
        self.connection.close()


class WSGIServer(StreamServer):

    handler_class = HttpProtocol
    base_env = {'GATEWAY_INTERFACE': 'CGI/1.1',
                'SERVER_SOFTWARE': 'gevent/%d.%d Python/%d.%d' % (gevent.version_info[:2] + sys.version_info[:2]),
                'SCRIPT_NAME': '',
                'wsgi.version': (1, 0),
                'wsgi.url_scheme': 'http',
                'wsgi.errors': sys.stderr,
                'wsgi.multithread': False,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False}

    def __init__(self, listener, application, backlog=None, pool=None, handler_class=None, log=sys.stderr, **ssl_args):
        StreamServer.__init__(self, listener, backlog=backlog, pool=pool, log=log)
        if hasattr(listener, 'do_handshake'):
            self.base_env['wsgi.url_scheme'] = 'https'
        self.application = application

    def get_environ(self):
        return self.base_env.copy()

    def pre_start(self):
        StreamServer.pre_start(self)
        env = self.base_env.copy()
        env.update( {'SERVER_NAME': socket.getfqdn(self.server_host),
                     'SERVER_PORT': str(self.server_port) } )
        self.base_env = env

    def handle(self, socket, address):
        handler = self.handler_class(socket, address, self)
        handler.handle()

