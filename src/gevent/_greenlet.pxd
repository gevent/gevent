# cython: auto_pickle=False

cimport cython
from gevent.__ident cimport IdentRegistry
from gevent.__hub_local cimport get_hub_noargs as get_hub
from gevent.__waiter cimport Waiter

cdef bint _PYPY
cdef sys_getframe
cdef sys_exc_info
cdef Timeout
cdef GreenletExit
cdef InvalidSwitchError

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

cdef extern from "Python.h":

    ctypedef class types.CodeType [object PyCodeObject]:
        pass

cdef extern from "frameobject.h":

    ctypedef class types.FrameType [object PyFrameObject]:
        cdef CodeType f_code
        cdef int f_lineno
        # We can't declare this in the object, because it's
        # allowed to be NULL, and Cython can't handle that.
        # We have to go through the python machinery to get a
        # proper None instead.
        # cdef FrameType f_back

cdef void _init()

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
@cython.freelist(1000)
cdef class _Frame:
    cdef readonly CodeType f_code
    cdef readonly int f_lineno
    cdef readonly _Frame f_back


@cython.final
@cython.locals(frames=list,frame=FrameType)
cdef inline list _extract_stack(int limit)

@cython.final
@cython.locals(previous=_Frame, frame=tuple, f=_Frame)
cdef _Frame _Frame_from_list(list frames)


cdef class Greenlet(greenlet):
    cdef readonly object value
    cdef readonly tuple args
    cdef readonly dict kwargs
    cdef readonly object spawning_greenlet
    cdef public dict spawn_tree_locals

    # This is accessed with getattr() dynamically so it
    # must be visible to Python
    cdef readonly list _spawning_stack_frames

    cdef list _links
    cdef tuple _exc_info
    cdef object _notifier
    cdef object _start_event
    cdef str _formatted_info
    cdef object _ident

    cpdef bint has_links(self)
    cpdef join(self, timeout=*)
    cpdef bint ready(self)
    cpdef bint successful(self)
    cpdef rawlink(self, object callback)
    cpdef str _formatinfo(self)

    @cython.locals(reg=IdentRegistry)
    cdef _get_minimal_ident(self)


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

    # Hmm, declaring _raise_exception causes issues when _imap
    # is also compiled.
    # TypeError: wrap() takes exactly one argument (0 given)
    # cpdef _raise_exception(self)



# Declare a bunch of imports as cdefs so they can
# be accessed directly as static vars without
# doing a module global lookup. This is especially important
# for spawning greenlets.
cdef _greenlet__init__
cdef _threadlocal
cdef get_hub_class
cdef wref

cdef dump_traceback
cdef load_traceback
cdef Waiter
cdef wait
cdef iwait
cdef reraise
cpdef GEVENT_CONFIG


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
