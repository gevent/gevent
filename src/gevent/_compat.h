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
   /* _PyInterpreterFrame moved to the internal C API in Python 3.11 */
#  include <internal/pycore_frame.h>
#else
#  define GEVENT_PY311 0
#  define _PyCFrame CFrame
#endif

/* FrameType and CodeType changed a lot in 3.11. */
#if GREENLET_PY311
typedef PyObject PyFrameObject;
#else
#include <frameobject.h>
#if PY_MAJOR_VERSION < 3 || PY_MINOR_VERSION < 9
/* these were added in 3.9, though they officially became stable in 3.10 */
static void* PyFrame_GetBack(PyFrameObject* frame)
{
    return (PyObject*)((PyFrameObject*)frame)->f_back;
}

static PyObject* PyFrame_GetCode(PyFrameObject* frame)
{
    return (PyObject*)((PyFrameObject*)frame)->f_code;
}
#endif /* support 3.8 and below. */
#endif

#ifdef __cplusplus
}
#endif
#endif /* _COMPAT_H */
