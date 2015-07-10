cdef class Semaphore:
    cdef public int counter
    cdef readonly object _links
    cdef readonly object _notifier
    cdef public int _dirty

    cpdef locked(self)
    cpdef release(self)
    cpdef rawlink(self, object callback)
    cpdef unlink(self, object callback)
    cpdef wait(self, object timeout=*)
    cpdef acquire(self, int blocking=*, object timeout=*)
    cpdef __enter__(self)
    cpdef __exit__(self, object t, object v, object tb)
