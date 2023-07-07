"""
Secure Sockets Layer (SSL/TLS) module.
"""

from gevent._util import copy_globals

# things we expect to override, here for static analysis
def wrap_socket(_sock, **_kwargs):
    # pylint:disable=unused-argument
    raise NotImplementedError()


from gevent import _ssl3 as _source


copy_globals(_source, globals())
