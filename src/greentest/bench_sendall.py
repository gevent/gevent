#! /usr/bin/env python
from __future__ import print_function
import time
from gevent import socket
from gevent.server import StreamServer


def recvall(socket, addr):
    while socket.recv(4096):
        pass


def main():
    server = StreamServer(("127.0.0.1", 0), recvall)
    server.start()

    length = 50 * 0x100000
    data = b"x" * length

    spent_total = 0
    N = 10

    conn = socket.create_connection((server.server_host, server.server_port))
    for i in range(N):
        start = time.time()
        conn.sendall(data)
        spent = time.time() - start
        print("%.2f MB/s" % (length / spent / 0x100000))
        spent_total += spent

    print("~ %.2f MB/s" % (length * N / spent_total / 0x100000))
    server.stop()


if __name__ == "__main__":
    main()
