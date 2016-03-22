"""Backwards compatibility alias for :mod:`gevent.pywsgi`.

In the past, this used libevent's http support, but that was dropped
with the introduction of libev. libevent's http support had several
limitations, including not supporting stream, not supporting
pipelining, and not supporting SSL.

.. deprecated:: 1.1
   Use :mod:`gevent.pywsgi`
"""

from gevent.pywsgi import * # pylint:disable=wildcard-import,unused-wildcard-import
import gevent.pywsgi as _pywsgi
__all__ = _pywsgi.__all__
del _pywsgi
