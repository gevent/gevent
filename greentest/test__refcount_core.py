import weakref


class Dummy:
    def __init__(self):
        __import__('gevent.core')


assert weakref.ref(Dummy())() is None

from gevent import socket

assert weakref.ref(socket.socket())() is None
