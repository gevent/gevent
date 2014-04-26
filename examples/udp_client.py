# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
"""Send a datagram to localhost:9000 and receive a datagram back.

Usage: python udp_client.py MESSAGE

Make sure you're running a UDP server on port 9000 (see udp_server.py).

There's nothing gevent-specific here.
"""
from __future__ import print_function
import sys
from gevent import socket

address = ('localhost', 9000)
message = ' '.join(sys.argv[1:])
sock = socket.socket(type=socket.SOCK_DGRAM)
sock.connect(address)
print('Sending %s bytes to %s:%s' % ((len(message), ) + address))
sock.send(message.encode())
data, address = sock.recvfrom(8192)
print('%s:%s: got %r' % (address + (data, )))
