#define DEFINE_CALLBACK(WATCHER_LC, WATCHER_TYPE) \
    static void gevent_callback_##WATCHER_LC(struct ev_loop *, void *, int);


#define DEFINE_CALLBACKS               \
    DEFINE_CALLBACK(io, IO);           \
    DEFINE_CALLBACK(timer, Timer);     \
    DEFINE_CALLBACK(signal, Signal);   \
    DEFINE_CALLBACK(idle, Idle);       \
    DEFINE_CALLBACK(prepare, Prepare); \
    DEFINE_CALLBACK(fork, Fork);       \
    DEFINE_CALLBACK(async, Async);


DEFINE_CALLBACKS


static void gevent_signal_check(struct ev_loop *, void *, int);
struct PyGeventLoopObject;
static void gevent_handle_error(struct PyGeventLoopObject* loop, PyObject* context);

#if defined(_WIN32)
static void gevent_periodic_signal_check(struct ev_loop *, void *, int);
#endif
