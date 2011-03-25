static void gevent_io_callback(struct ev_loop*, struct ev_io*, int);
static void gevent_simple_callback(struct ev_loop *, void *, int);
static void gevent_signal_check(struct ev_loop *, void *, int);

#if defined(GEVENT_WINDOWS)
static void gevent_periodic_signal_check(struct ev_loop *, void *, int);
#endif
