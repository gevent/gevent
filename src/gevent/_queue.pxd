cimport cython
from gevent.__waiter cimport Waiter
from gevent._event cimport Event

cdef _heappush
cdef _heappop
cdef _heapify

@cython.final
cdef _safe_remove(deq, item)

@cython.final
@cython.internal
cdef class ItemWaiter(Waiter):
    cdef readonly item
    cdef readonly queue

cdef class Queue:
    cdef __weakref__
    cdef readonly hub
    cdef readonly queue

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

    cpdef put(self, item, block=*, timeout=*)
    cpdef put_nowait(self, item)

    cdef __get_or_peek(self, method, block, timeout)

    cpdef get(self, block=*, timeout=*)
    cpdef get_nowait(self)
    cpdef peek(self, block=*, timeout=*)
    cpdef peek_nowait(self)

    cdef _schedule_unlock(self)

@cython.final
cdef class UnboundQueue(Queue):
    pass

cdef class PriorityQueue(Queue):
    pass

cdef class LifoQueue(Queue):
    pass

cdef class JoinableQueue(Queue):
    cdef Event _cond
    cdef readonly int unfinished_tasks


cdef class Channel:
    cdef __weakref__
    cdef readonly getters
    cdef readonly putters
    cdef readonly hub
    cdef _event_unlock

    cpdef get(self, block=*, timeout=*)
    cpdef get_nowait(self)

    cdef _schedule_unlock(self)
