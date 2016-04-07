from gevent.select import select
from gevent.server import StreamServer
from gevent import socket


def handler(socket, address):
    while True:
        if not socket.recv(1000):
            break


server = StreamServer(('127.0.0.1', 0), handler)
server.start()

s = socket.create_connection(('127.0.0.1', server.server_port))
while True:
    select([], [s.fileno()] * 10, [])
