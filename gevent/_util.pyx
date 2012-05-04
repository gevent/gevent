from python cimport *
import os


__all__ = ['set_exc_info']


def set_exc_info(object type, object value):
    cdef PyThreadState* tstate = PyThreadState_GET()
    Py_XDECREF(tstate.exc_type)
    Py_XDECREF(tstate.exc_value)
    Py_XDECREF(tstate.exc_traceback)
    if type is None:
        tstate.exc_type = NULL
    else:
        Py_INCREF(<PyObjectPtr>type)
        tstate.exc_type = <PyObjectPtr>type
    if value is None:
        tstate.exc_value = NULL
    else:
        Py_INCREF(<PyObjectPtr>value)
        tstate.exc_value = <PyObjectPtr>value
    tstate.exc_traceback = NULL


# We implement __del__s in Cython so that they are safe against signals


def SocketAdapter__del__(self, close=os.close):
    fileno = self._fileno
    if fileno is not None:
        self._fileno = None
        if self._close:
            close(fileno)


def noop(self):
    pass
