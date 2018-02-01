"""Backwards compatibility alias for :mod:`gevent.resolver.cares`.

.. deprecated:: 1.3
   Use :mod:`gevent.resolver.cares`
"""

from gevent.resolver.cares import * # pylint:disable=wildcard-import,unused-wildcard-import
import gevent.resolver.cares as _cares
__all__ = _cares.__all__
del _cares
