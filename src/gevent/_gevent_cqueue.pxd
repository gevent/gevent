cimport cython
from gevent._gevent_c_waiter cimport Waiter
from gevent._gevent_cevent cimport Event
from gevent._gevent_c_hub_local cimport get_hub_noargs as get_hub

cdef bint _greenlet_imported
cdef _heappush
cdef _heappop
cdef _heapify
cdef _Empty
cdef _Full
cdef Timeout
cdef InvalidSwitchError

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


@cython.final
cdef _safe_remove(deq, item)

cdef class Queue:
    cdef __weakref__
    cdef readonly hub
    cdef readonly queue
    cdef readonly bint is_shutdown

    cdef getters
    cdef putters

    cdef _event_unlock
    cdef Py_ssize_t _maxsize

    cpdef _get(self)
    cpdef _put(self, item)
    cpdef _peek(self)

    cpdef Py_ssize_t qsize(self)
    cpdef bint empty(self)
    cpdef bint full(self)
    cpdef _create_queue(self, items=*)

    cpdef put(self, item, block=*, timeout=*)
    cpdef put_nowait(self, item)

    cdef __get_or_peek(self, method, block, timeout)

    cpdef get(self, block=*, timeout=*)
    cpdef get_nowait(self)
    cpdef peek(self, block=*, timeout=*)
    cpdef peek_nowait(self)
    cpdef shutdown(self, immediate=*)

    cdef _schedule_unlock(self)
    cdef _drain_for_immediate_shutdown(self)


@cython.final
@cython.internal
cdef class ItemWaiter(Waiter):
    cdef readonly item
    cdef readonly Queue queue

###
# XXX: Disabling Cython.final here pending a release > Cython 3.0.11
# because it breaks on GCC. See https://github.com/gevent/gevent/issues/2049#issuecomment-2404700280
# Restore when new cython is released.
#
# @cython.final
###
cdef class UnboundQueue(Queue):
    pass

cdef class PriorityQueue(Queue):
    pass


cdef class JoinableQueue(Queue):
    cdef Event _cond
    cdef readonly int unfinished_tasks
    cdef _did_put_task(self)


cdef class LifoQueue(JoinableQueue):
    pass

cdef class Channel:
    cdef __weakref__
    cdef readonly getters
    cdef readonly putters
    cdef readonly hub
    cdef _event_unlock

    cpdef get(self, block=*, timeout=*)
    cpdef get_nowait(self)

    cdef _schedule_unlock(self)
