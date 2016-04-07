from __future__ import absolute_import, print_function


__all__ = [

]

import gevent.libuv._corecffi as _corecffi # pylint:disable=no-name-in-module,import-error

ffi = _corecffi.ffi  # pylint:disable=no-member
libuv = _corecffi.lib  # pylint:disable=no-member
