#define GIL_DECLARE  PyGILState_STATE ___save
#define GIL_ENSURE  ___save = PyGILState_Ensure();
#define GIL_RELEASE  PyGILState_Release(___save);

void* gevent_realloc(void* ptr, size_t size)
{
    // libev is interesting and assumes that everything can be
    // done with realloc(), assuming that passing in a size of 0 means to
    // free the pointer. But the C/++ standard explicitly says that
    // this is undefined. So this wrapper function exists to do it all.
    GIL_DECLARE;
    void* result;
    if(!size && !ptr) {
	// libev for some reason often tries to free(NULL); I won't specutale
	// why. No need to acquire the GIL or do anything in that case.
	return NULL;
    }

    // Using PyObject_* APIs to get access to pymalloc allocator on
    // all versions of CPython; in Python 3, PyMem_* and PyObject_* use
    // the same allocator, but in Python 2, only PyObject_* uses pymalloc.
    GIL_ENSURE;

    if(!size) {
	PyObject_Free(ptr);
	result = NULL;
    }
    else {
	result = PyObject_Realloc(ptr, size);
    }
    GIL_RELEASE;
    return result;
}
