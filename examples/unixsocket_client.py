from __future__ import print_function
# gevent-test-requires-resource: unixsocket_server
import socket

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("./unixsocket_server.py.sock")
s.send('GET / HTTP/1.0\r\n\r\n')
data = s.recv(1024)
print('received %s bytes' % len(data))
print(data)
s.close()
