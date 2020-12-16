cimport cython

from gevent._gevent_c_greenlet_primitives cimport SwitchOutGreenletWithLoop
from gevent._gevent_c_abstract_linkable cimport AbstractLinkable
from gevent._gevent_c_hub_local cimport get_hub_if_exists
from gevent._gevent_c_hub_local cimport get_hub_noargs as get_hub

cdef InvalidThreadUseError
cdef LoopExit
cdef Timeout
cdef _native_sleep
cdef monotonic
cdef spawn_raw

cdef class _LockReleaseLink(object):
    cdef object lock


cdef class Semaphore(AbstractLinkable):
    cdef public int counter

    cdef long _multithreaded

    cpdef bint locked(self)
    cpdef int release(self) except -1000
    # We don't really want this to be public, but
    # threadpool uses it
    cpdef _start_notify(self)
    cpdef int wait(self, object timeout=*) except -1000
    @cython.locals(
        success=bint,
        e=Exception,
        ex=Exception,
        args=tuple,
    )
    cpdef bint acquire(self, bint blocking=*, object timeout=*) except -1000
    cpdef __enter__(self)
    cpdef __exit__(self, object t, object v, object tb)

    @cython.locals(
        hub_for_this_thread=SwitchOutGreenletWithLoop,
        owning_hub=SwitchOutGreenletWithLoop,
    )
    cdef __acquire_from_other_thread(self, tuple args, bint blocking, timeout)
    cpdef __acquire_from_other_thread_cb(self, list results, bint blocking, timeout, thread_lock)

    cdef __add_link(self, link)
    cdef __acquire_using_two_hubs(self,
                                  SwitchOutGreenletWithLoop hub_for_this_thread,
                                  current_greenlet,
                                  timeout)
    cdef __acquire_using_other_hub(self, SwitchOutGreenletWithLoop owning_hub, timeout)
    cdef bint __acquire_without_hubs(self, timeout)
    cdef bint __spin_on_native_lock(self, thread_lock, timeout)

cdef class BoundedSemaphore(Semaphore):
    cdef readonly int _initial_value

    cpdef int release(self) except -1000
