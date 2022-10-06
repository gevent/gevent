#ifndef _COMPAT_H
#define _COMPAT_H

/**
 * Compatibility helpers for things that are better handled at C
 * compilation time rather than Cython code generation time.
 */

#include <Python.h>

#ifdef __cplusplus
extern "C" {
#endif

#if PY_VERSION_HEX >= 0x30B00A6
#  define GEVENT_PY311 1
#else
#  define GEVENT_PY311 0
#  define _PyCFrame CFrame
#endif

/* FrameType and CodeType changed a lot in 3.11. */
#if GREENLET_PY311
   /* _PyInterpreterFrame moved to the internal C API in Python 3.11 */
#  include <internal/pycore_frame.h>
#else
#include <frameobject.h>
#if PY_MAJOR_VERSION < 3 || (PY_MAJOR_VERSION >= 3 && PY_MINOR_VERSION < 9)
/* these were added in 3.9, though they officially became stable in 3.10 */
/* the official versions of these functions return strong references, so we
   need to increment the refcount before returning, not just to match the
   official functions, but to match what Cython expects an API like this to
   return. Otherwise we get crashes. */
static void* PyFrame_GetBack(PyFrameObject* frame)
{
    PyObject* result = (PyObject*)((PyFrameObject*)frame)->f_back;
    Py_XINCREF(result);
    return result;
}

static PyObject* PyFrame_GetCode(PyFrameObject* frame)
{
    PyObject* result = (PyObject*)((PyFrameObject*)frame)->f_code;
    Py_XINCREF(result);
    return result;
}
#endif /* support 3.8 and below. */
#endif

#ifdef __cplusplus
}
#endif
#endif /* _COMPAT_H */
