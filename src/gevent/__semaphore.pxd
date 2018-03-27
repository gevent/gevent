cimport cython

from gevent.__hub_local cimport get_hub_noargs as get_hub
cdef Timeout

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


cdef void _init()


cdef class Semaphore:
    cdef public int counter
    cdef readonly list _links
    cdef readonly object _notifier
    cdef public int _dirty
    cdef object __weakref__

    cpdef bint locked(self)
    cpdef int release(self) except -1000
    cpdef rawlink(self, object callback)
    cpdef unlink(self, object callback)
    cpdef _start_notify(self)
    cpdef _notify_links(self)
    cdef _do_wait(self, object timeout)
    cpdef int wait(self, object timeout=*) except -1000
    cpdef bint acquire(self, int blocking=*, object timeout=*) except -1000
    cpdef __enter__(self)
    cpdef __exit__(self, object t, object v, object tb)

cdef class BoundedSemaphore(Semaphore):
    cdef readonly int _initial_value

    cpdef int release(self) except -1000
