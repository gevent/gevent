import sys
import traceback
from gevent import core
from gevent.greenlet import Greenlet
from gevent.event import Event
from gevent.util import wrap_errors
from gevent.timeout import Timeout
import _socket as socket

class HTTPServer(object):

    spawn = Greenlet.spawn # set to None to avoid spawning at all
    backlog = 5

    def __init__(self, handle=None, spawn='default'):
        self.listeners = []
        self._stopped_event = Event()
        self._no_connections_event = Event()
        self._requests = {} # maps connection -> list of requests
        self.http = core.http()
        self.http.set_gencb(self._cb_request)
        if handle is not None:
            self.handle = handle
        if spawn != 'default':
            self.spawn = spawn

    def start(self, socket_or_address, backlog=None):
        """Start accepting connections"""
        fileno = getattr(socket_or_address, 'fileno', None)
        if fileno is not None:
            fd = fileno()
            s = socket_or_address
        else:
            s = self.make_listener(socket_or_address, backlog=backlog)
            fd = s.fileno()
        self.http.accept(fd)
        self.listeners.append(s)
        self._stopped_event.clear()
        if self._requests:
            self._no_connections_event.clear()
        else:
            self._no_connections_event.set()
        return s

    def make_listener(self, address, backlog=None):
        if backlog is None:
            backlog = self.backlog
        s = socket.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) | 1)
        except socket.error:
            pass
        s.bind(address)
        s.listen(backlog)
        return s

    def stop(self, timeout=0):
        """Shutdown the server."""
        for s in self.listeners:
            s.close()
        self.socket = []
        #2. Set "keep-alive" connections to "close"
        # TODO
        #3a. set low timeout (min(1s, timeout or 1)) on events belonging to connection (to kill long-polling connections
        # TODO
        #3. Wait until every connection is closed or timeout expires
        if self._requests:
            t = Timeout.start_new(timeout)
            try:
                try:
                    self._no_connections_event.wait(timeout=timeout)
                except Timeout, ex:
                    if t is not ex:
                        raise
            finally:
                t.cancel()
        #4. forcefull close all the connections
        # TODO
        #5. free http instance
        self.http = None
        #6. notify event created in serve_forever()
        self._stopped_event.set()

    def handle(self, request):
        request.send_reply(200, 'OK', 'It works!')

    def _cb_connection_close(self, connection):
        # make sure requests belonging to this connection cannot be accessed anymore
        # because they've been freed by libevent
        requests = self._requests.pop(connection._obj, [])
        for r in requests:
            r.detach()
        if not self._requests:
            self._no_connections_event.set()

    def _cb_request_processed(self, g):
        request = g._request
        g._request = None
        if request:
            if not g.successful():
                self.reply_error(request)
            requests = self._requests.get(request.connection._obj)
            if requests is not None:
                requests.remove(request)

    def _cb_request(self, request):
        try:
            spawn = self.spawn
            request.connection.set_closecb(self)
            self._requests.setdefault(request.connection._obj, []).append(request)
            if spawn is None:
                self.handle(request)
            else:
                g = spawn(wrap_errors(core.HttpRequestDeleted, self.handle), request)
                rawlink = getattr(g, 'rawlink', None)
                if rawlink is not None:
                    g._request = request
                    rawlink(self._cb_request_processed)
        except:
            traceback.print_exc()
            try:
                sys.stderr.write('Failed to handle request: %s\n\n' % (request, ))
            except:
                pass
            self.reply_error(request)

    def reply_error(self, request):
        try:
            if request.response == (0, None):
                request.send_reply(500, 'Internal Server Error', '<h1>Internal Server Error</h1>')
        except core.HttpRequestDeleted:
            pass

    def serve_forever(self, *args, **kwargs):
        stop_timeout = kwargs.pop('stop_timeout', 0)
        self.start(*args, **kwargs)
        try:
            self._stopped_event.wait()
        finally:
            Greenlet.spawn(self.stop, timeout=stop_timeout).join()

