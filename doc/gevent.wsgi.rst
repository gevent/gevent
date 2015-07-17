
==============================================================================
 :mod:`gevent.wsgi` -- Backwards compatibility alias for :mod:`gevent.pywsgi`
==============================================================================

In the past, this module used libevent's http support, but that was dropped
with the introduction of libev. libevent's http support had several
limitations, including not supporting stream, not supporting
pipelining, and not supporting SSL.

This module now simply re-exports the contents of the
:mod:`gevent.pywsgi` module.

.. deprecated:: 1.1
   Use :mod:`gevent.pywsgi`
