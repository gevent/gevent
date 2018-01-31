"""Backwards compatibility alias for :mod:`gevent.resolver.thread`.

.. deprecated:: 1.3
   Use :mod:`gevent.resolver.cares`
"""

from gevent.resolver.thread import * # pylint:disable=wildcard-import,unused-wildcard-import
import gevent.resolver.thread as _thread
__all__ = _thread.__all__
del _thread
