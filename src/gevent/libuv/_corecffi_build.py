# pylint: disable=no-member

# This module is only used to create and compile the gevent._corecffi module;
# nothing should be directly imported from it except `ffi`, which should only be
# used for `ffi.compile()`; programs should import gevent._corecfffi.
# However, because we are using "out-of-line" mode, it is necessary to examine
# this file to know what functions are created and available on the generated
# module.
from __future__ import absolute_import, print_function
import sys
import os
import os.path # pylint:disable=no-name-in-module
import struct

__all__ = []


def system_bits():
    return struct.calcsize('P') * 8


def st_nlink_type():
    if sys.platform == "darwin" or sys.platform.startswith("freebsd"):
        return "short"
    if system_bits() == 32:
        return "unsigned long"
    return "long long"


from cffi import FFI
ffi = FFI()

thisdir = os.path.dirname(os.path.abspath(__file__))
def read_source(name):
    with open(os.path.join(thisdir, name), 'r') as f:
        return f.read()

_cdef = read_source('_corecffi_cdef.c')
_source = read_source('_corecffi_source.c')

_cdef = _cdef.replace('#define GEVENT_ST_NLINK_T int', '')
_cdef = _cdef.replace('#define GEVENT_STRUCT_DONE int', '')
_cdef = _cdef.replace('GEVENT_ST_NLINK_T', st_nlink_type())
_cdef = _cdef.replace("GEVENT_STRUCT_DONE _;", '...;')


# if sys.platform.startswith('win'):
#     # We must have the vfd_open, etc, functions on
#     # Windows. But on other platforms, going through
#     # CFFI to just return the file-descriptor is slower
#     # than just doing it in Python, so we check for and
#     # workaround their absence in corecffi.py
#     _cdef += """
# typedef int... vfd_socket_t;
# int vfd_open(vfd_socket_t);
# vfd_socket_t vfd_get(int);
# void vfd_free(int);
# """

setup_py_dir = os.path.abspath(os.path.join(thisdir, '..', '..', '..'))
libuv_dir = os.path.abspath(os.path.join(setup_py_dir, 'deps', 'libuv'))
sys.path.append(setup_py_dir)

include_dirs = [
    thisdir, # libev_vfd.h
    os.path.join(libuv_dir, 'include'),
]


library_dirs = [
    os.path.join(libuv_dir, '.libs')
]

from _setuplibuv import LIBUV_LIBRARIES # pylint:disable=import-error
from _setuplibuv import LIBUV # pylint:disable=import-error

ffi.cdef(_cdef)
ffi.set_source('gevent.libuv._corecffi', _source,
               include_dirs=include_dirs,
               library_dirs=library_dirs,
               extra_objects=list(LIBUV.extra_objects),
               extra_link_args=list(LIBUV.extra_link_args),
               libraries=list(LIBUV_LIBRARIES))

if __name__ == '__main__':
    ffi.compile()
