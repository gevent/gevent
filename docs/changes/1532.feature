Add ``gevent.selectors`` containing ``GeventSelector``. This selector
implementation uses gevent details to attempt to reduce overhead when
polling many file descriptors, only some of which become ready at any
given time.

This is monkey-patched as ``selectors.DefaultSelector`` by default.

This is available on Python 2 if the ``selectors2`` backport is
installed. (This backport is installed automatically using the
``recommended`` extra.) When monkey-patching, ``selectors`` is made
available as an alias to this module.
