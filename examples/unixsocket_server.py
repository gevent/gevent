# gevent-test-requires-resource: unixsocket_client
import os
from gevent.pywsgi import WSGIServer
from gevent import socket


def application(environ, start_response):
    assert environ
    start_response('200 OK', [])
    return []


if __name__ == '__main__':
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sockname = './' + os.path.basename(__file__) + '.sock'
    if os.path.exists(sockname):
        os.remove(sockname)
    listener.bind(sockname)
    listener.listen(1)
    WSGIServer(listener, application).serve_forever()
