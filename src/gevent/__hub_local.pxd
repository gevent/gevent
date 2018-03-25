cdef _threadlocal

cpdef get_hub_class()
cpdef get_hub_if_exists()
cpdef set_hub(hub)
cpdef get_loop()
cpdef set_loop(loop)


# XXX: TODO: Move the definition of TrackedRawGreenlet
# into a file that can be cython compiled so get_hub can
# return that.
cpdef get_hub_noargs()
