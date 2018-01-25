# cython: auto_pickle=False

cimport cython

@cython.final
@cython.internal
cdef class _wrefdict(dict):
   cdef object __weakref__

@cython.final
@cython.internal
cdef class _thread_deleted:
    cdef object idt
    cdef object wrdicts


@cython.final
@cython.internal
cdef class _local_deleted:
    cdef str key
    cdef object wrthread
    cdef _thread_deleted thread_deleted

@cython.final
@cython.internal
cdef class _localimpl:
    cdef str key
    cdef _wrefdict dicts
    cdef tuple localargs
    cdef object __weakref__


cdef dict _localimpl_create_dict(_localimpl self)
cdef inline dict _localimpl_get_dict(_localimpl self)


cdef class local:
    cdef _localimpl _local__impl

cdef inline dict _local_get_dict(local self)

cdef _local__copy_dict_from(local self, _localimpl impl, dict duplicate)
