from gevent.hub import PY3


if PY3:
    from gevent import _ssl3 as _source
else:
    from gevent import _ssl2 as _source


for key in _source.__dict__:
    if key.startswith('__') and key not in '__implements__ __all__ __imports__'.split():
        continue
    globals()[key] = getattr(_source, key)
