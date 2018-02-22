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


@cython.final
@cython.locals(
               previous=_Frame,
               first=_Frame,
               next_frame=_Frame)
cdef _Frame _extract_stack(int limit, _Frame f_back)



cdef class Greenlet(greenlet):
    cdef readonly object value
    cdef readonly args
    cdef readonly object spawning_greenlet
    cdef public dict spawn_tree_locals

    cdef readonly _Frame spawning_stack

    cdef list _links
    cdef tuple _exc_info
    cdef object _notifier
    cdef object _start_event
    cdef dict _kwargs

    cpdef bint has_links(self)
    cpdef join(self, timeout=*)
    cpdef bint ready(self)
    cpdef bint successful(self)
    cpdef rawlink(self, object callback)

    cdef bint __started_but_aborted(self)
    cdef bint __start_cancelled_by_kill(self)
    cdef bint __start_pending(self)
    cdef bint __never_started_or_killed(self)
    cdef bint __start_completed(self)
    cdef __handle_death_before_start(self, tuple args)

    cdef __cancel_start(self)

    cdef _report_result(self, object result)
    cdef _report_error(self, tuple exc_info)
    # This is used as the target of a callback
    # from the loop, and so needs to be a cpdef
    cpdef _notify_links(self)
    # IMapUnordered greenlets in pools need to access this
    # method
    cpdef _raise_exception(self)

# Declare a bunch of imports as cdefs so they can
# be accessed directly as static vars without
# doing a module global lookup. This is especially important
# for spawning greenlets.
cdef _greenlet__init__
cdef get_hub
cdef wref
cdef getcurrent

cdef Timeout
cdef dump_traceback
cdef load_traceback
cdef Waiter
cdef wait
cdef iwait
cdef reraise
cdef InvalidSwitchError


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
