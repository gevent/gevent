:mod:`gevent.core` - Low-level wrappers around libevent
=======================================================

.. automodule:: gevent.core

events
------

.. autoclass:: event(evtype, handle, callback[, arg])
    :members:
    :undoc-members:
.. autoclass:: read_event
    :members:
    :undoc-members:
.. autoclass:: write_event
    :members:
    :undoc-members:
.. autoclass:: timer
    :members:
    :undoc-members:
.. autoclass:: signal
    :members:
    :undoc-members:
.. autoclass:: active_event
    :members:
    :undoc-members:

event loop
----------

.. autofunction:: init
.. autofunction:: dispatch
.. autofunction:: loop
.. autofunction:: get_version
.. autofunction:: get_method
.. autofunction:: get_header_version


evdns
-----

.. autofunction:: dns_init
.. autofunction:: dns_shutdown
.. autofunction:: dns_resolve_ipv4
.. autofunction:: dns_resolve_ipv6
.. autofunction:: dns_resolve_reverse
.. autofunction:: dns_resolve_reverse_ipv6


evbuffer
--------

.. autoclass:: buffer
    :members:
    :undoc-members:


evhttp
------

.. autoclass:: http_request
    :members:
    :undoc-members:
.. autoclass:: http_connection
    :members:
    :undoc-members:
.. autoclass:: http
    :members:
    :undoc-members:

