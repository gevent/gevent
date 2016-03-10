# Copyright (c) 2012 Denis Bilenko. See LICENSE for details.
"""A simple UDP server.

For every message received, it sends a reply back.

You can use udp_client.py to send a message.
"""
from __future__ import print_function
from gevent.server import DatagramServer


class EchoServer(DatagramServer):

    def handle(self, data, address): # pylint:disable=method-hidden
        print('%s: got %r' % (address[0], data))
        self.socket.sendto(('Received %s bytes' % len(data)).encode('utf-8'), address)


if __name__ == '__main__':
    print('Receiving datagrams on :9000')
    EchoServer(':9000').serve_forever()
