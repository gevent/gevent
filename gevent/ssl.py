from gevent.hub import PYGTE279


if PYGTE279:
    from gevent import _sslgte279 as _source
else:
    from gevent import _ssl2 as _source


for key in _source.__dict__:
    if key.startswith('__') and key not in '__implements__ __all__ __imports__'.split():
        continue
    globals()[key] = getattr(_source, key)
