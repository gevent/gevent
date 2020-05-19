cimport cython

from gevent._gevent_c_greenlet_primitives cimport SwitchOutGreenletWithLoop
from gevent._gevent_c_hub_local cimport get_hub_noargs as get_hub
from gevent._gevent_c_hub_local cimport get_hub_if_exists

cdef InvalidSwitchError
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

cdef class AbstractLinkable(object):
   # We declare the __weakref__ here in the base (even though
   # that's not really what we want) as a workaround for a Cython
   # issue we see reliably on 3.7b4 and sometimes on 3.6. See
   # https://github.com/cython/cython/issues/2270
   cdef object __weakref__

   cdef readonly SwitchOutGreenletWithLoop hub

   cdef _notifier
   cdef list _links
   cdef bint _notify_all

   cpdef linkcount(self)
   cpdef rawlink(self, callback)
   cpdef bint ready(self)
   cpdef unlink(self, callback)

   cdef _check_and_notify(self)
   cdef void _capture_hub(self, bint create)
   cdef __wait_to_be_notified(self, bint rawlink)
   cdef void __unlink_all(self, obj) # suppress exceptions

   @cython.nonecheck(False)
   cdef _notify_link_list(self, list links)

   @cython.nonecheck(False)
   cpdef _notify_links(self, list arrived_while_waiting)

   cpdef _drop_lock_for_switch_out(self)
   cpdef _acquire_lock_for_switch_in(self)

   cdef _wait_core(self, timeout, catch=*)
   cdef _wait_return_value(self, waited, wait_success)
   cdef _wait(self, timeout=*)
