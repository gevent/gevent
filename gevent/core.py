# Copyright (c) 2009-2015 Denis Bilenko and gevent contributors. See LICENSE for details.
from __future__ import absolute_import

import os

try:
    if os.environ.get('GEVENT_CORE_CFFI_ONLY'):
        raise ImportError("Not attempting corecext")

    from gevent import corecext as _core
except ImportError:
    # CFFI/PyPy
    from gevent import corecffi as _core

for item in dir(_core):
    if item.startswith('__'):
        continue
    globals()[item] = getattr(_core, item)


__all__ = _core.__all__
