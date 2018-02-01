"""Backwards compatibility alias for :mod:`gevent.resolver.ares`.

.. deprecated:: 1.3
   Use :mod:`gevent.resolver.ares`
"""

from gevent.resolver.ares import * # pylint:disable=wildcard-import,unused-wildcard-import
import gevent.resolver.ares as _ares
__all__ = _ares.__all__
del _ares
