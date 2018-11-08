import weakref


class Dummy:
    def __init__(self):
        __import__('gevent.core')

try:
    assert weakref.ref(Dummy())() is None

    from gevent import socket
    s = socket.socket()
    r = weakref.ref(s)
    s.close()
    del s
    assert r() is None
except AssertionError:
    import sys
    if hasattr(sys, 'pypy_version_info'):
        # PyPy uses a non refcounted GC which may defer
        # the collection of the weakref, unlike CPython
        pass
    else:
        raise
