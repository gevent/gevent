# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
import sys
import traceback
from urllib import unquote
from datetime import datetime
socket = __import__('socket')

import gevent
from gevent.http import HTTPServer


__all__ = ['WSGIServer',
           'WSGIHandler']


class buffer_proxy(object):

    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, item):
        assert item != '_obj'
        return getattr(self._obj, item)

    def __iter__(self):
        while len(self._obj):
            yield self._obj.readline()


class WSGIHandler(object):

    def __init__(self, request):
        self.request = request
        self.code = None
        self.reason = None
        self.headers = None
        self.data = []

    def start_response(self, status, headers, exc_info=None):
        if not exc_info:
            assert self.reason is None, 'start_response was already called'
        else:
            self.data = []
        code, self.reason = status.split(' ', 1)
        self.code = int(code)
        self.headers = headers
        return self.write

    def write(self, data):
        self.data.append(data)

    def end(self, env):
        assert self.headers is not None, 'Application did not call start_response'
        has_content_length = False
        for header, value in self.headers:
            self.request.add_output_header(header, str(value))
            if header == 'Content-Length':
                has_content_length = True
        data = ''.join(self.data)
        if not has_content_length:
            self.request.add_output_header('Content-Length', str(len(data)))

        # QQQ work around bug in libevent 2.0.2 (and probably in older)
        if (self.request.find_input_header('Transfer-Encoding') or '').lower() == 'chunked':
            # if input is chunked, libevent assumes output chunked as well regardless
            # of presence of 'Content-Length'
            self.request.remove_output_header('Content-Length')
        # QQQ end of work around
        # QQQ when this is fixed, add version guard

        SERVER_SOFTWARE = env.get('SERVER_SOFTWARE')
        if SERVER_SOFTWARE and not self.request.find_output_header('Server'):
            self.request.add_output_header('Server', SERVER_SOFTWARE)

        self.send_reply(self.code, self.reason, data)

    def send_reply(self, code, reason, data):
        self.request.send_reply(code, reason, data)
        self.log_request(len(data))

    def format_request(self, length='-'):
        req = self.request
        referer = req.find_input_header('Referer') or '-'
        agent = req.find_input_header('User-Agent') or '-'
        # QQQ fix datetime format
        now = datetime.now().replace(microsecond=0)
        args = (req.remote_host, now, req.typestr, req.uri,
                req.major, req.minor, req.response_code, length, referer, agent)
        return '%s - - [%s] "%s %s HTTP/%s.%s" %s %s "%s" "%s"' % args

    def log_request(self, *args):
        print self.format_request(*args)

    def prepare_env(self, req, server):
        env = server.base_env.copy()
        if '?' in req.uri:
            path, query = req.uri.split('?', 1)
        else:
            path, query = req.uri, ''
        path = unquote(path)
        env.update({'REQUEST_METHOD': req.typestr,
                    'PATH_INFO': path,
                    'QUERY_STRING': query,
                    'SERVER_PROTOCOL': 'HTTP/%d.%d' % req.version,
                    'REMOTE_ADDR': req.remote_host,
                    'REMOTE_PORT': str(req.remote_port),
                    'wsgi.input': buffer_proxy(req.input_buffer)})
        for header, value in req.get_input_headers():
            header = header.replace('-', '_').upper()
            if header not in ('CONTENT_LENGTH', 'CONTENT_TYPE'):
                header = 'HTTP_' + header
            env[header] = value
        return env

    def handle(self, server):
        req = self.request
        env = self.prepare_env(req, server)
        try:
            try:
                result = server.application(env, self.start_response)
                try:
                    self.data.extend(result)
                finally:
                    if hasattr(result, 'close'):
                        result.close()
            except:
                traceback.print_exc()
                try:
                    sys.stderr.write('Failed to handle request:\n  request = %s\n  application = %s\n\n' % (req, server.application))
                except:
                    traceback.print_exc()
                server.reply_error(self.request)
                self = None
                return
        finally:
            if self is not None:
                self.end(env)


class WSGIServer(HTTPServer):

    handler_class = WSGIHandler

    base_env = {'GATEWAY_INTERFACE': 'CGI/1.1',
                'SERVER_SOFTWARE': 'gevent/%d.%d Python/%d.%d' % (gevent.version_info[:2] + sys.version_info[:2]),
                'SCRIPT_NAME': '',
                'wsgi.version': (1, 0),
                'wsgi.url_scheme': 'http',
                'wsgi.errors': sys.stderr,
                'wsgi.multithread': False,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False}

    def __init__(self, socket_or_address, application, **kwargs):
        handler_class = kwargs.pop('handler_class', None)
        if handler_class is not None:
            self.handler_class = handler_class
        HTTPServer.__init__(self, **kwargs)
        self.address = socket_or_address
        self.application = application

    @property
    def server_host(self):
        return self.address[0]

    @property
    def server_port(self):
        return self.address[1]

    def start(self):
        if self.listeners:
            raise AssertionError('WSGIServer.start() cannot be called more than once')
        sock = HTTPServer.start(self, self.address, backlog=self.backlog)
        self.address = sock.getsockname()
        env = self.base_env.copy()
        env.update( {'SERVER_NAME': socket.getfqdn(self.server_host),
                     'SERVER_PORT': str(self.server_port) } )
        self.base_env = env
        return sock

    def handle(self, req):
        handler = self.handler_class(req)
        handler.handle(self)


def extract_application(filename):
    import imp
    import os
    basename = os.path.basename(filename)
    if '.' in basename:
        name, suffix = basename.rsplit('.', 1)
    else:
        name, suffix = basename, ''
    module = imp.load_module(name, open(filename), filename, (suffix, 'r', imp.PY_SOURCE))
    return module.application


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-p', '--port', default='8080', type='int')
    parser.add_option('--interface', default='127.0.0.1')
    parser.add_option('--no-spawn', dest='spawn', default=True, action='store_false')
    options, args = parser.parse_args()
    if len(args) == 1:
        filename = args[0]
        try:
            application = extract_application(filename)
        except AttributeError:
            sys.exit("Could not find application in %s" % filename)
        if options.spawn:
            spawn = 'default'
        else:
            spawn = None
        server = WSGIServer((options.interface, options.port), application, spawn=spawn)
        print 'Serving %s on %s:%s' % (filename, options.interface, options.port)
        server.serve_forever()
    else:
        sys.stderr.write("USAGE: %s /path/to/app.wsgi\napp.wsgi is a python script defining 'application' callable\n" % sys.argv[0])


