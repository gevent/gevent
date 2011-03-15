static void handle_error(PyObject* loop, PyObject* arg) {
    PyThreadState *tstate;
    PyObject *type, *value, *traceback, *handler, *result;
    int reported;
    tstate = PyThreadState_GET();
    type = tstate->curexc_type;
    if (!type)
        return;
    value = tstate->curexc_value;
    traceback = tstate->curexc_traceback;
    if (!value) value = Py_None;
    if (!traceback) traceback = Py_None;
    Py_INCREF(type);
    Py_INCREF(value);
    Py_INCREF(traceback);

    reported = 0;

    handler = PyObject_GetAttrString(loop, "handle_error");
    if (handler) {
        if (handler != Py_None) {
            PyObject* tuple;
            if (arg) {
                tuple = PyTuple_New(4);
            }
            else {
                tuple = PyTuple_New(3);
            }
            if (tuple) {
                reported = 1;
                Py_INCREF(arg);
                PyTuple_SET_ITEM(tuple, 0, arg);
                PyTuple_SET_ITEM(tuple, 1, type);
                PyTuple_SET_ITEM(tuple, 2, value);
                PyTuple_SET_ITEM(tuple, 3, traceback);
                PyErr_Clear();
                result = PyObject_Call(handler, tuple, NULL);
                if (result) {
                    Py_DECREF(result);
                }
                else {
                    PyErr_WriteUnraisable(handler);
                }
                Py_DECREF(tuple);
            }
            Py_DECREF(handler);
        }
    }

    if (!reported) {
        PyErr_WriteUnraisable(loop);
        Py_DECREF(type);
        Py_DECREF(value);
        Py_DECREF(traceback);
    }

    PyErr_Clear();
}

static inline void handle_signal_error(PyObject* loop) {
    Py_INCREF(Py_None);
    handle_error(loop, Py_None);
    Py_DECREF(Py_None);
}

/* Calls callback(watcher, revents) and reports errors.
 * Returns 1 on success, 0 on failure
 * */
static inline int _callback(PyObject* callback, PyObject* watcher, int revents, PyObject* loop) {
    int success;
    PyObject *py_revents, *tuple, *result;
    PyErr_CheckSignals();
    if (PyErr_Occurred()) handle_signal_error(loop);

    success = 0;

    py_revents = PyInt_FromLong(revents);
    if (py_revents) {
        tuple = PyTuple_New(2);
        if (tuple) {
            Py_INCREF(watcher);
            PyTuple_SET_ITEM(tuple, 0, watcher);
            PyTuple_SET_ITEM(tuple, 1, py_revents);
            result = PyObject_Call(callback, tuple, NULL);
            if (result) {
                success = 1;
                Py_DECREF(result);
            }
            else {
                handle_error(loop, watcher);
            }
            Py_DECREF(tuple);
        }
        else {
            Py_DECREF(py_revents);
        }
    }
    PyErr_Clear();
    return success;
}


/* Calls callback(*args) and reports errors */
static void _callback_simple(PyObject* callback, PyObject* watcher, PyObject* args, PyObject* loop) {
    PyObject* result;
    PyErr_CheckSignals();
    if (PyErr_Occurred()) handle_signal_error(loop);

    result = PyObject_Call(callback, args, NULL);

    if (result) {
        Py_DECREF(result);
    }
    else {
        handle_error(loop, watcher);
    }
    PyErr_Clear();
}


#define GET_OBJECT(EV_PTR, PY_TYPE, MEMBER) \
    ((struct PY_TYPE *)(((char *)EV_PTR) - offsetof(struct PY_TYPE, MEMBER)))


#ifdef WITH_THREAD
#define GIL_ENSURE  PyGILState_STATE ___save = PyGILState_Ensure();
#define GIL_RELEASE  PyGILState_Release(___save);
#else
#define GIL_ENSURE
#define GIL_RELEASE
#endif


static inline void stop(PyObject* self) {
    PyObject *result, *callable;
    callable = PyObject_GetAttrString(self, "stop");
    if (callable) {
        result = PyObject_Call(callable, __pyx_empty_tuple, NULL);
        if (result) {
            Py_DECREF(result);
        }
        else {
            PyErr_WriteUnraisable(callable);
        }
        Py_DECREF(callable);
    }
}


#define timer_offsetof offsetof(struct __pyx_obj_6gevent_4core_timer, _watcher)
#define signal_offsetof offsetof(struct __pyx_obj_6gevent_4core_signal, _watcher)
#define idle_offsetof offsetof(struct __pyx_obj_6gevent_4core_idle, _watcher)
#define prepare_offsetof offsetof(struct __pyx_obj_6gevent_4core_prepare, _watcher)
#define callback_offsetof offsetof(struct __pyx_obj_6gevent_4core_callback, _watcher)

#define CHECK_OFFSETOF (timer_offsetof == signal_offsetof) && (timer_offsetof == idle_offsetof) && (timer_offsetof == prepare_offsetof) && (timer_offsetof == callback_offsetof)


static void simple_callback(struct ev_loop *_loop, void *watcher, int revents) {
    char STATIC_ASSERTION__same_offsetof[(CHECK_OFFSETOF)?1:-1];
    struct __pyx_obj_6gevent_4core_timer *self;
    GIL_ENSURE;
    /* we use this callback for all watchers, not just timer
     * we can do this, because layout of struct members is the same for all watchers */
    self = ((struct __pyx_obj_6gevent_4core_timer *)(((char *)watcher) - timer_offsetof));
    Py_INCREF(self);
    _callback_simple(self->callback, (PyObject*)self, self->args, (PyObject*)self->loop);
    if (!ev_active(watcher)) {
        stop((PyObject*)self);
    }
    Py_DECREF(self);
    GIL_RELEASE;
}

static void io_callback(struct ev_loop *loop, struct ev_io *watcher, int revents) {
    struct __pyx_obj_6gevent_4core_io *self;
    GIL_ENSURE;
    self = GET_OBJECT(watcher, __pyx_obj_6gevent_4core_io, _watcher);
    Py_INCREF(self);
    if (!_callback(self->callback, (PyObject*)self, revents, (PyObject*)self->loop)) {
        stop((PyObject*)self);
    }
    Py_DECREF(self);
    GIL_RELEASE;
}

static void signal_check(struct ev_loop *_loop, void *watcher, int revents) {
    struct __pyx_obj_6gevent_4core_loop *loop;
    GIL_ENSURE;
    PyErr_CheckSignals();
    loop = GET_OBJECT(watcher, __pyx_obj_6gevent_4core_loop, _signal_checker);
    if (PyErr_Occurred()) handle_signal_error((PyObject*)loop);
    GIL_RELEASE;
}

static void periodic_signal_check(struct ev_loop *_loop, void *watcher, int revents) {
    struct __pyx_obj_6gevent_4core_loop *loop;
    GIL_ENSURE;
    PyErr_CheckSignals();
    loop = GET_OBJECT(watcher, __pyx_obj_6gevent_4core_loop, _periodic_signal_checker);
    if (PyErr_Occurred()) handle_signal_error((PyObject*)loop);
    GIL_RELEASE;
}
