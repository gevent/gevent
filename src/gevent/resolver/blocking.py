# Copyright (c) 2018  gevent contributors. See LICENSE for details.

import _socket

class Resolver(object):
    """
    A resolver that directly uses the system's resolver functions.
    """

    def __init__(self, hub=None):
        pass

    def close(self):
        pass

    for method in (
            'gethostbyname',
            'gethostbyname_ex',
            'getaddrinfo',
            'gethostbyaddr',
            'getnameinfo'
    ):
        locals()[method] = staticmethod(getattr(_socket, method))
