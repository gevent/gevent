import gevent.monkey
gevent.monkey.patch_all()

import socket
import multiprocessing

# Make sure that using the resolver in a forked process
# doesn't hang forever.


def block():
    socket.getaddrinfo('localhost', 8001)


def main():
    socket.getaddrinfo('localhost', 8001)

    p = multiprocessing.Process(target=block)
    p.start()
    p.join()

if __name__ == '__main__':
    main()
