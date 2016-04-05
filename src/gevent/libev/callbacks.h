#define DEFINE_CALLBACK(WATCHER_LC, WATCHER_TYPE) \
    static void gevent_callback_##WATCHER_LC(struct ev_loop *, void *, int);


#define DEFINE_CALLBACKS0              \
    DEFINE_CALLBACK(io, IO);           \
    DEFINE_CALLBACK(timer, Timer);     \
    DEFINE_CALLBACK(signal, Signal);   \
    DEFINE_CALLBACK(idle, Idle);       \
    DEFINE_CALLBACK(prepare, Prepare); \
    DEFINE_CALLBACK(check, Check);     \
    DEFINE_CALLBACK(fork, Fork);       \
    DEFINE_CALLBACK(async, Async);     \
    DEFINE_CALLBACK(stat, Stat);


#ifndef _WIN32

#define DEFINE_CALLBACKS               \
    DEFINE_CALLBACKS0                  \
    DEFINE_CALLBACK(child, Child)

#else

#define DEFINE_CALLBACKS DEFINE_CALLBACKS0

#endif


DEFINE_CALLBACKS


static void gevent_run_callbacks(struct ev_loop *, void *, int);
struct PyGeventLoopObject;
static void gevent_handle_error(struct PyGeventLoopObject* loop, PyObject* context);
struct PyGeventCallbackObject;
static void gevent_call(struct PyGeventLoopObject* loop, struct PyGeventCallbackObject* cb);

#if defined(_WIN32)
static void gevent_periodic_signal_check(struct ev_loop *, void *, int);
#endif

static void gevent_noop(struct ev_loop *_loop, void *watcher, int revents) { }
