# cython: auto_pickle=False

cimport cython


cdef extern from "greenlet/greenlet.h":

  ctypedef class greenlet.greenlet [object PyGreenlet]:
      pass


cdef class SpawnedLink:
    cdef public object callback


@cython.final
cdef class SuccessSpawnedLink(SpawnedLink):
    pass

@cython.final
cdef class FailureSpawnedLink(SpawnedLink):
    pass

@cython.final
@cython.internal
cdef class _Frame:
    cdef readonly object f_code
    cdef readonly int f_lineno
    cdef public _Frame f_back


cdef class Greenlet(greenlet):
    cdef readonly object value
    cdef readonly args
    cdef readonly object spawning_greenlet
    cdef public dict spawn_tree_locals

    cdef readonly _Frame spawning_stack
    # A test case reads this, otherwise they would
    # be private
    cdef readonly list _links

    cdef object tuple _exc_info
    cdef object _notifier
    cdef object _start_event
    cdef dict _kwargs


    cdef bint __started_but_aborted(self)
    cdef bint __start_cancelled_by_kill(self)
    cdef bint __start_pending(self)
    cdef bint __never_started_or_killed(self)
    cdef bint __start_completed(self)

    cdef __cancel_start(self)

    cdef _report_result(self, object result)
    cdef _report_error(self, tuple exc_info)


@cython.final
@cython.internal
cdef class _dummy_event:
    cdef readonly bint pending
    cdef readonly bint active

    cpdef stop(self)
    cpdef start(self, cb)
    cpdef close(self)

cdef _dummy_event _cancelled_start_event
cdef _dummy_event _start_completed_event


@cython.locals(diehards=list)
cdef _killall3(list greenlets, object exception, object waiter)
cdef _killall(list greenlets, object exception)

@cython.locals(done=list)
cpdef joinall(greenlets, timeout=*, raise_error=*, count=*)
