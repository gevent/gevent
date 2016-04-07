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

libuv_dir = os.path.abspath(os.path.join(thisdir, '..', '..', '..', 'deps', 'libuv'))

include_dirs = [
    thisdir, # libev_vfd.h
    os.path.join(libuv_dir, 'include'),
]


library_dirs = [
    os.path.join(libuv_dir, '.libs')
]

if sys.platform.startswith('win'):
    libuv_lib = os.path.join(libuv_dir, 'Release', 'lib', 'libuv.lib')
    extra_link_args = ['/NODEFAULTLIB:libcmt', '/LTCG']
    extra_objects = [libuv_lib]
else:
    libuv_lib = os.path.join(libuv_dir, '.libs', 'libuv.a')
    extra_objects = [libuv_lib]
    extra_link_args = []

LIBUV_LIBRARIES = []
if sys.platform.startswith('linux'):
    LIBUV_LIBRARIES.append('rt')
elif sys.platform.startswith("win"):
    LIBUV_LIBRARIES.append('advapi32')
    LIBUV_LIBRARIES.append('iphlpapi')
    LIBUV_LIBRARIES.append('psapi')
    LIBUV_LIBRARIES.append('shell32')
    LIBUV_LIBRARIES.append('userenv')
    LIBUV_LIBRARIES.append('ws2_32')
elif sys.platform.startswith('freebsd'):
    LIBUV_LIBRARIES.append('kvm')

ffi.cdef(_cdef)
ffi.set_source('gevent.libuv._corecffi', _source,
               include_dirs=include_dirs,
               library_dirs=library_dirs,
               extra_objects=extra_objects,
               extra_link_args=extra_link_args,
               libraries=LIBUV_LIBRARIES)

if __name__ == '__main__':
    ffi.compile()
