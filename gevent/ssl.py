"""
Secure Sockets Layer (SSL/TLS) module.
"""
from gevent.hub import PY2


if PY2:
    if hasattr(__import__('ssl'), 'SSLContext'):
        # It's not sufficient to check for >= 2.7.9; some distributions
        # have backported most of PEP 466. Try to accommodate them. See Issue #702.
        # We're just about to import ssl anyway so it's fine to import it here, just
        # don't pollute the namespace
        from gevent import _sslgte279 as _source
    else:
        from gevent import _ssl2 as _source
else:
    # Py3
    from gevent import _ssl3 as _source


for key in _source.__dict__:
    if key.startswith('__') and key not in '__implements__ __all__ __imports__'.split():
        continue
    globals()[key] = getattr(_source, key)
