#! /usr/bin/env python
import time
from gevent import server, socket


class MyServer(server.StreamServer):

    def handle(self, socket, addr):
        while True:
            d = socket.recv(4096)
            if not d:
                break


def main():
    server = MyServer(("127.0.0.1", 0))
    server.start()

    length = 50*0x100000
    data = "x" * length
    
    spent_total = 0
    N = 10

    conn = socket.create_connection((server.server_host, server.server_port))
    for i in range(N):
        start = time.time()
        conn.sendall(data)
        spent = time.time() - start
        print "%.2f MB/s" % (length / spent / 0x100000)
        spent_total += spent

    print "== %.2f MB/s" % (length * N / spent_total / 0x100000)


if __name__=="__main__":
    main()

