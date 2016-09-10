/* libev interface */

#define EV_MINPRI ...
#define EV_MAXPRI ...

#define EV_VERSION_MAJOR ...
#define EV_VERSION_MINOR ...

#define EV_UNDEF ...
#define EV_NONE ...
#define EV_READ ...
#define EV_WRITE ...
#define EV__IOFDSET ...
#define EV_TIMER ...
#define EV_PERIODIC ...
#define EV_SIGNAL ...
#define EV_CHILD ...
#define EV_STAT ...
#define EV_IDLE ...
#define EV_PREPARE ...
#define EV_CHECK ...
#define EV_EMBED ...
#define EV_FORK ...
#define EV_CLEANUP ...
#define EV_ASYNC ...
#define EV_CUSTOM ...
#define EV_ERROR ...

#define EVFLAG_AUTO ...
#define EVFLAG_NOENV ...
#define EVFLAG_FORKCHECK ...
#define EVFLAG_NOINOTIFY ...
#define EVFLAG_SIGNALFD ...
#define EVFLAG_NOSIGMASK ...

#define EVBACKEND_SELECT ...
#define EVBACKEND_POLL ...
#define EVBACKEND_EPOLL ...
#define EVBACKEND_KQUEUE ...
#define EVBACKEND_DEVPOLL ...
#define EVBACKEND_PORT ...
/* #define EVBACKEND_IOCP ... */

#define EVBACKEND_ALL ...
#define EVBACKEND_MASK ...

#define EVRUN_NOWAIT ...
#define EVRUN_ONCE ...

#define EVBREAK_CANCEL ...
#define EVBREAK_ONE ...
#define EVBREAK_ALL ...

/* markers for the CFFI parser. Replaced when the string is read. */
#define GEVENT_STRUCT_DONE int
#define GEVENT_ST_NLINK_T int

struct ev_loop {
    int backend_fd;
    int activecnt;
    GEVENT_STRUCT_DONE _;
};

// Watcher types
// base for all watchers
struct ev_watcher{
	GEVENT_STRUCT_DONE _;
};

struct ev_io {
    int fd;
    int events;
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_timer {
    double at;
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_signal {
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_idle {
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_prepare {
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_check {
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_fork {
    void* data;
    GEVENT_STRUCT_DONE _;
};
struct ev_async {
    void* data;
    GEVENT_STRUCT_DONE _;
};

struct ev_child {
    int pid;
    int rpid;
    int rstatus;
    void* data;
    GEVENT_STRUCT_DONE _;
};

struct stat {
    GEVENT_ST_NLINK_T st_nlink;
    GEVENT_STRUCT_DONE _;
};

struct ev_stat {
    struct stat attr;
    const char* path;
    struct stat prev;
    double interval;
    void* data;
    GEVENT_STRUCT_DONE _;
};

typedef double ev_tstamp;

int ev_version_major();
int ev_version_minor();

unsigned int ev_supported_backends (void);
unsigned int ev_recommended_backends (void);
unsigned int ev_embeddable_backends (void);

ev_tstamp ev_time (void);
void ev_set_syserr_cb(void *);

int ev_priority(void*);
void ev_set_priority(void*, int);

int ev_is_pending(void*);
int ev_is_active(void*);
void ev_io_init(struct ev_io*, void* callback, int fd, int events);
void ev_io_start(struct ev_loop*, struct ev_io*);
void ev_io_stop(struct ev_loop*, struct ev_io*);
void ev_feed_event(struct ev_loop*, void*, int);

void ev_timer_init(struct ev_timer*, void *callback, double, double);
void ev_timer_start(struct ev_loop*, struct ev_timer*);
void ev_timer_stop(struct ev_loop*, struct ev_timer*);
void ev_timer_again(struct ev_loop*, struct ev_timer*);

void ev_signal_init(struct ev_signal*, void* callback, int);
void ev_signal_start(struct ev_loop*, struct ev_signal*);
void ev_signal_stop(struct ev_loop*, struct ev_signal*);

void ev_idle_init(struct ev_idle*, void* callback);
void ev_idle_start(struct ev_loop*, struct ev_idle*);
void ev_idle_stop(struct ev_loop*, struct ev_idle*);

void ev_prepare_init(struct ev_prepare*, void* callback);
void ev_prepare_start(struct ev_loop*, struct ev_prepare*);
void ev_prepare_stop(struct ev_loop*, struct ev_prepare*);

void ev_check_init(struct ev_check*, void* callback);
void ev_check_start(struct ev_loop*, struct ev_check*);
void ev_check_stop(struct ev_loop*, struct ev_check*);

void ev_fork_init(struct ev_fork*, void* callback);
void ev_fork_start(struct ev_loop*, struct ev_fork*);
void ev_fork_stop(struct ev_loop*, struct ev_fork*);

void ev_async_init(struct ev_async*, void* callback);
void ev_async_start(struct ev_loop*, struct ev_async*);
void ev_async_stop(struct ev_loop*, struct ev_async*);
void ev_async_send(struct ev_loop*, struct ev_async*);
int ev_async_pending(struct ev_async*);

void ev_child_init(struct ev_child*, void* callback, int, int);
void ev_child_start(struct ev_loop*, struct ev_child*);
void ev_child_stop(struct ev_loop*, struct ev_child*);

void ev_stat_init(struct ev_stat*, void* callback, char*, double);
void ev_stat_start(struct ev_loop*, struct ev_stat*);
void ev_stat_stop(struct ev_loop*, struct ev_stat*);

struct ev_loop *ev_default_loop (unsigned int flags);
struct ev_loop* ev_loop_new(unsigned int flags);
void ev_loop_destroy(struct ev_loop*);
void ev_loop_fork(struct ev_loop*);
int ev_is_default_loop (struct ev_loop *);
unsigned int ev_iteration(struct ev_loop*);
unsigned int ev_depth(struct ev_loop*);
unsigned int ev_backend(struct ev_loop*);
void ev_verify(struct ev_loop*);
void ev_run(struct ev_loop*, int flags);

ev_tstamp ev_now (struct ev_loop *);
void ev_now_update (struct ev_loop *); /* update event loop time */
void ev_ref(struct ev_loop*);
void ev_unref(struct ev_loop*);
void ev_break(struct ev_loop*, int);
unsigned int ev_pending_count(struct ev_loop*);

struct ev_loop* gevent_ev_default_loop(unsigned int flags);
void gevent_install_sigchld_handler();
void gevent_reset_sigchld_handler();

void (*gevent_noop)(struct ev_loop *_loop, struct ev_timer *w, int revents);
void ev_sleep (ev_tstamp delay); /* sleep for a while */

/* gevent callbacks */
static int (*python_callback)(void* handle, int revents);
static void (*python_handle_error)(void* handle, int revents);
static void (*python_stop)(void* handle);

/*
 * We use a single C callback for every watcher type, which in turn calls the
 * Python callbacks. The ev_watcher pointer type can be used for every watcher type
 * because they all start with the same members---libev itself relies on this. Each
 * watcher types has a 'void* data' that stores the CFFI handle to the Python watcher
 * object.
 */
static void _gevent_generic_callback(struct ev_loop* loop, struct ev_watcher* watcher, int revents);
