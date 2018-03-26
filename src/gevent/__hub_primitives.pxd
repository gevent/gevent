cimport cython

from gevent.__greenlet_primitives cimport SwitchOutGreenletWithLoop
from gevent.__hub_local cimport get_hub_noargs as get_hub

from gevent.__waiter cimport Waiter
from gevent.__waiter cimport MultipleWaiter

cdef InvalidSwitchError
cdef _waiter
cdef _greenlet_primitives
cdef traceback


cdef extern from "greenlet/greenlet.h":

    ctypedef class greenlet.greenlet [object PyGreenlet]:
        pass

    # These are actually macros and so much be included
    # (defined) in each .pxd, as are the two functions
    # that call them.
    greenlet PyGreenlet_GetCurrent()
    void PyGreenlet_Import()

@cython.final
cdef inline greenlet getcurrent():
    return PyGreenlet_GetCurrent()

cdef bint _greenlet_imported

cdef inline void greenlet_init():
    global _greenlet_imported
    if not _greenlet_imported:
        PyGreenlet_Import()
        _greenlet_imported = True


cdef class WaitOperationsGreenlet(SwitchOutGreenletWithLoop):

    cpdef wait(self, watcher)
    cpdef cancel_wait(self, watcher, error, close_watcher=*)
    cpdef _cancel_wait(self, watcher, error, close_watcher)

cdef class _WaitIterator:
    cdef SwitchOutGreenletWithLoop _hub
    cdef MultipleWaiter _waiter
    cdef _switch
    cdef _timeout
    cdef _objects
    cdef _timer
    cdef Py_ssize_t _count
    cdef bint _begun



    cdef _cleanup(self)

cpdef iwait(objects, timeout=*, count=*)
cpdef wait(objects=*, timeout=*, count=*)
