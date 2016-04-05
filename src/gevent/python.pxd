cdef extern from "Python.h":
    struct PyObject:
        pass
    ctypedef PyObject* PyObjectPtr "PyObject*"
    void   Py_INCREF(PyObjectPtr)
    void   Py_DECREF(PyObjectPtr)
    void   Py_XDECREF(PyObjectPtr)
    int    Py_ReprEnter(PyObjectPtr)
    void   Py_ReprLeave(PyObjectPtr)
    int    PyCallable_Check(PyObjectPtr)

cdef extern from "frameobject.h":
    ctypedef struct PyThreadState:
        PyObjectPtr exc_type
        PyObjectPtr exc_value
        PyObjectPtr exc_traceback
    PyThreadState* PyThreadState_GET()
