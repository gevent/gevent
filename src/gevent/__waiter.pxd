cimport cython

cdef sys
cdef ConcurrentObjectUseError

from gevent.__hub_local cimport get_hub_noargs as get_hub

cdef bint _greenlet_imported

cdef extern from "greenlet/greenlet.h":

    ctypedef class greenlet.greenlet [object PyGreenlet]:
        pass

    # These are actually macros and so much be included
    # (defined) in each .pxd, as are the two functions
    # that call them.
    greenlet PyGreenlet_GetCurrent()
    void PyGreenlet_Import()

cdef inline greenlet getcurrent():
    return PyGreenlet_GetCurrent()

cdef inline void greenlet_init():
    global _greenlet_imported
    if not _greenlet_imported:
        PyGreenlet_Import()
        _greenlet_imported = True


cdef class Waiter:
    cdef readonly hub
    cdef readonly greenlet
    cdef readonly value
    cdef _exception

@cython.final
@cython.internal
cdef class MultipleWaiter(Waiter):
    cdef list _values
