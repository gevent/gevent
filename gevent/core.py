from gevent.hub import PYPY

if PYPY:
    from gevent import corecffi as _core
else:
    # NOTE: On CPython, this file is never imported (and there is no
    # corecext module). Instead, the core.so file that should be build
    # is imported in preference.
    # NOTE: CFFI is now usable on CPython, and the performance is
    # mostly comparable, so this could be refactored to allow that
    # (along with the makefile, etc)
    from gevent import corecext as _core


for item in dir(_core):
    if item.startswith('__'):
        continue
    globals()[item] = getattr(_core, item)


__all__ = _core.__all__
