# cython: auto_pickle=False
cdef class _wrefdict(dict):
   cdef object __weakref__

cdef class _localimpl:
    cdef str key
    cdef dict dicts
    cdef tuple localargs
    cdef object __weakref__

    cdef dict create_dict(self)
    cdef dict get_dict(self)

cdef class local:
    cdef _localimpl _local__impl

    cdef _local__copy_dict_from(self, _localimpl impl, dict duplicate)
