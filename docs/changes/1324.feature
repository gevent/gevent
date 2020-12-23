Make :class:`gevent.Greenlet` objects function as context managers.
When the ``with`` suite finishes, execution doesn't continue until the
greenlet is finished. This can be a simpler alternative to a
:class:`gevent.pool.Group` when the lifetime of greenlets can be
lexically scoped.

Suggested by André Caron.
