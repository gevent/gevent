static void gevent_callback(struct ev_loop *, void *, int);
static void gevent_signal_check(struct ev_loop *, void *, int);
struct PyGeventLoopObject;
static void gevent_handle_error(struct PyGeventLoopObject* loop, PyObject* where);

#if defined(_WIN32)
static void gevent_periodic_signal_check(struct ev_loop *, void *, int);
#endif
