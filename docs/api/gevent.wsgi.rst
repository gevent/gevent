==========================================================
 ``gevent.wsgi`` -- Historical note only; does not exist
==========================================================

.. warning::

   Beginning in gevent 1.3, this module no longer exists.

Starting in gevent 1.0a1 (2011), this module was nothing more than
an alias for :mod:`gevent.pywsgi`, which is what should be used instead.

Prior to gevent 1.0, when gevent was based on libevent,
``gevent.wsgi`` used libevent's http support, but that was dropped
with the introduction of libev. libevent's http support had several
limitations, including not supporting stream, not supporting
pipelining, and not supporting SSL.
