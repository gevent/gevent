from gevent.hub import PYPY

if PYPY:
    from gevent import corecffi as _core
else:
    from gevent import corecext as _core


for item in dir(_core):
    if item.startswith('__'):
        continue
    globals()[item] = getattr(_core, item)


__all__ = _core.__all__
