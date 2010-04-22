# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
from gevent import core
from gevent.baseserver import BaseServer


__all__ = ['HTTPServer']


class HTTPServer(BaseServer):
    """An HTTP server based on libevent-http.
    
    *handle* is called with one argument: an :class:`gevent.core.http_request` instance.
    """

    def __init__(self, listener, handle=None, backlog=None, spawn='default'):
        BaseServer.__init__(self, listener, handle=handle, backlog=backlog, spawn=spawn)
        self.http = None

    @property
    def started(self):
        return self.http is not None

    def _on_request(self, request):
        spawn = self.spawn
        if spawn is None:
            self.handle(request)
        else:
            if self.full():
                request._default_response_code = 503
            else:
                spawn(self.handle, request)

    def start_accepting(self):
        self.http = core.http(self._on_request)
        self.http.accept(self.socket.fileno())

    def stop_accepting(self):
        self.http = None

