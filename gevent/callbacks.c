static void gevent_handle_error(struct PyGeventLoopObject* loop, PyObject* where) {
    PyThreadState *tstate;
    PyObject *type, *value, *traceback, *handler, *result, *tuple;
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

    PyErr_Clear();

    result = ((struct __pyx_vtabstruct_6gevent_4core_loop *)loop->__pyx_vtab)->handle_error(loop, where, type, value, traceback, 0);

    if (result) {
        Py_DECREF(result);
    }
    else {
        PyErr_Print();
        PyErr_Clear();
    }

    Py_DECREF(type);
    Py_DECREF(value);
    Py_DECREF(traceback);
}


static inline void gevent_check_signals(struct PyGeventLoopObject* loop) {
    PyErr_CheckSignals();
    if (PyErr_Occurred()) gevent_handle_error(loop, Py_None);
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


static inline void gevent_stop(struct PyGeventTimerObject* watcher) {
    PyObject *result, *callable;
    result = ((struct __pyx_vtabstruct_6gevent_4core_timer *)watcher->__pyx_vtab)->stop(watcher, 0);
    if (result) {
        Py_DECREF(result);
    }
    else {
        gevent_handle_error(watcher->loop, (PyObject*)watcher);
    }
}


#define io_offsetof offsetof(struct PyGeventIOObject, _watcher)
#define timer_offsetof offsetof(struct PyGeventTimerObject, _watcher)
#define signal_offsetof offsetof(struct PyGeventSignalObject, _watcher)
#define idle_offsetof offsetof(struct PyGeventIdleObject, _watcher)
#define prepare_offsetof offsetof(struct PyGeventPrepareObject, _watcher)
#define callback_offsetof offsetof(struct PyGeventCallbackObject, _watcher)

#define CHECK_OFFSETOF (timer_offsetof == signal_offsetof) && (timer_offsetof == idle_offsetof) && (timer_offsetof == prepare_offsetof) && (timer_offsetof == callback_offsetof) && (timer_offsetof == io_offsetof)


static void gevent_callback(struct ev_loop *_loop, void *c_watcher, int revents) {
    struct PyGeventTimerObject *watcher;
    PyObject *result, *py_events, *args;
    long length;
    GIL_ENSURE;
    /* we use this callback for all watchers, not just timer
     * we can do this, because layout of struct members is the same for all watchers */
    watcher = ((struct PyGeventTimerObject *)(((char *)c_watcher) - timer_offsetof));
    Py_INCREF((PyObject*)watcher);
    gevent_check_signals(watcher->loop);
    args = watcher->args;
    if (args == Py_None) {
        args = __pyx_empty_tuple;
    }
    length = PyTuple_Size(args);
    if (length < 0) {
        gevent_handle_error(watcher->loop, (PyObject*)watcher);
        goto end;
    }
    if (length > 0 && PyTuple_GET_ITEM(args, 0) == GEVENT_CORE_EVENTS) {
        py_events = PyInt_FromLong(revents);
        if (!py_events) {
            gevent_handle_error(watcher->loop, (PyObject*)watcher);
            goto end;
        }
        Py_DECREF(GEVENT_CORE_EVENTS);
        PyTuple_SET_ITEM(args, 0, py_events);
    }
    else {
        py_events = NULL;
    }
    /* no need to incref 'args'; PyEval_EvalCodeEx which eventually will be called will
     * increase the reference of every element in args*/
    result = PyObject_Call(watcher->_callback, args, NULL);
    if (result) {
        Py_DECREF(result);
    }
    else {
        gevent_handle_error(watcher->loop, (PyObject*)watcher);
        if (revents & (EV_READ|EV_WRITE)) {
            /* this was an 'io' watcher: not stopping it will likely to cause the failing callback to be called repeatedly */
            gevent_stop(watcher);
        }
    }
    if (py_events) {
        Py_DECREF(py_events);
        Py_INCREF(GEVENT_CORE_EVENTS);
        PyTuple_SET_ITEM(watcher->args, 0, GEVENT_CORE_EVENTS);
    }
    if (!ev_is_active(c_watcher)) {
        /* watcher will never be run again: calling stop() will clear 'callback' and 'args' */
        gevent_stop(watcher);
    }
end:
    Py_DECREF((PyObject*)watcher);
    GIL_RELEASE;
}


static void gevent_signal_check(struct ev_loop *_loop, void *watcher, int revents) {
    char STATIC_ASSERTION__same_offsetof[(CHECK_OFFSETOF)?1:-1];
    GIL_ENSURE;
    gevent_check_signals(GET_OBJECT(watcher, PyGeventLoopObject, _signal_checker));
    GIL_RELEASE;
}

#if defined(_WIN32)

static void gevent_periodic_signal_check(struct ev_loop *_loop, void *watcher, int revents) {
    GIL_ENSURE;
    gevent_check_signals(GET_OBJECT(watcher, PyGeventLoopObject, _periodic_signal_checker));
    GIL_RELEASE;
}

#endif
