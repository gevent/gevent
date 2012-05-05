# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
"""A simple UDP server.

For every message received, it sends a reply back.

You can use udp_client.py to send a message.
"""
from gevent.server import DatagramServer


class EchoServer(DatagramServer):

    def handle(self, data, address):
        print '%s: got %r' % (address[0], data)
        self.socket.sendto('Received %s bytes' % len(data), address)


if __name__ == '__main__':
    print 'Receiving datagrams on :9000'
    EchoServer(':9000').serve_forever()
