cimport cython

from gevent.__abstract_linkable cimport AbstractLinkable
cdef Timeout


cdef class Semaphore(AbstractLinkable):
    cdef public int counter

    cpdef bint locked(self)
    cpdef int release(self) except -1000
    # We don't really want this to be public, but
    # threadpool uses it
    cpdef _start_notify(self)
    cpdef int wait(self, object timeout=*) except -1000
    cpdef bint acquire(self, int blocking=*, object timeout=*) except -1000
    cpdef __enter__(self)
    cpdef __exit__(self, object t, object v, object tb)

cdef class BoundedSemaphore(Semaphore):
    cdef readonly int _initial_value

    cpdef int release(self) except -1000
