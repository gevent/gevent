/* access whether we built embedded or not */

#define LIBUV_EMBED ...

/* markers for the CFFI parser. Replaced when the string is read. */
#define GEVENT_STRUCT_DONE int
#define GEVENT_ST_NLINK_T int
#define GEVENT_UV_OS_SOCK_T int

#define UV_EBUSY ...

#define UV_VERSION_MAJOR ...
#define UV_VERSION_MINOR ...
#define UV_VERSION_PATCH ...

typedef enum {
	UV_RUN_DEFAULT = 0,
	UV_RUN_ONCE,
	UV_RUN_NOWAIT
} uv_run_mode;

typedef enum {
  UV_UNKNOWN_HANDLE = 0,
  UV_ASYNC,
  UV_CHECK,
  UV_FS_EVENT,
  UV_FS_POLL,
  UV_HANDLE,
  UV_IDLE,
  UV_NAMED_PIPE,
  UV_POLL,
  UV_PREPARE,
  UV_PROCESS,
  UV_STREAM,
  UV_TCP,
  UV_TIMER,
  UV_TTY,
  UV_UDP,
  UV_SIGNAL,
  UV_FILE,
  UV_HANDLE_TYPE_MAX
} uv_handle_type;

enum uv_poll_event {
	UV_READABLE = 1,
	UV_WRITABLE = 2,
	/* new in 1.9 */
	UV_DISCONNECT = 4,
	/* new in 1.14.0 */
	UV_PRIORITIZED = 8,
};

enum uv_fs_event {
	UV_RENAME = 1,
	UV_CHANGE = 2
};

enum uv_fs_event_flags {
	/*
	* By default, if the fs event watcher is given a directory name, we will
	* watch for all events in that directory. This flags overrides this behavior
	* and makes fs_event report only changes to the directory entry itself. This
	* flag does not affect individual files watched.
	* This flag is currently not implemented yet on any backend.
	*/
	UV_FS_EVENT_WATCH_ENTRY = 1,
	/*
	* By default uv_fs_event will try to use a kernel interface such as inotify
	* or kqueue to detect events. This may not work on remote filesystems such
	* as NFS mounts. This flag makes fs_event fall back to calling stat() on a
	* regular interval.
	* This flag is currently not implemented yet on any backend.
	*/
	UV_FS_EVENT_STAT = 2,
	/*
	* By default, event watcher, when watching directory, is not registering
	* (is ignoring) changes in it's subdirectories.
	* This flag will override this behaviour on platforms that support it.
	*/
	UV_FS_EVENT_RECURSIVE = 4
};

const char* uv_strerror(int);
const char* uv_err_name(int);
const char* uv_version_string(void);
const char* uv_handle_type_name(uv_handle_type type);

// handle structs and types
struct uv_loop_s {
	void* data;
	GEVENT_STRUCT_DONE _;
};
struct uv_handle_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};
struct uv_idle_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};
struct uv_prepare_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};
struct uv_timer_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};
struct uv_signal_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};
struct uv_poll_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};

struct uv_check_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};

struct uv_async_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};

struct uv_fs_event_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};

struct uv_fs_poll_s {
	struct uv_loop_s* loop;
	uv_handle_type type;
	void *data;
	GEVENT_STRUCT_DONE _;
};

typedef struct uv_loop_s uv_loop_t;
typedef struct uv_handle_s uv_handle_t;
typedef struct uv_idle_s uv_idle_t;
typedef struct uv_prepare_s uv_prepare_t;
typedef struct uv_timer_s uv_timer_t;
typedef struct uv_signal_s uv_signal_t;
typedef struct uv_poll_s uv_poll_t;
typedef struct uv_check_s uv_check_t;
typedef struct uv_async_s uv_async_t;
typedef struct uv_fs_event_s uv_fs_event_t;
typedef struct uv_fs_poll_s uv_fs_poll_t;


size_t uv_handle_size(uv_handle_type);

// callbacks with the same signature
typedef void (*uv_close_cb)(uv_handle_t *handle);
typedef void (*uv_idle_cb)(uv_idle_t *handle);
typedef void (*uv_timer_cb)(uv_timer_t *handle);
typedef void (*uv_check_cb)(uv_check_t* handle);
typedef void (*uv_async_cb)(uv_async_t* handle);
typedef void (*uv_prepare_cb)(uv_prepare_t *handle);

// callbacks with distinct sigs
typedef void (*uv_walk_cb)(uv_handle_t *handle, void *arg);
typedef void (*uv_poll_cb)(uv_poll_t *handle, int status, int events);
typedef void (*uv_signal_cb)(uv_signal_t *handle, int signum);

// Callback passed to uv_fs_event_start() which will be called
// repeatedly after the handle is started. If the handle was started
// with a directory the filename parameter will be a relative path to
// a file contained in the directory. The events parameter is an ORed
// mask of uv_fs_event elements.
typedef void (*uv_fs_event_cb)(uv_fs_event_t* handle, const char* filename, int events, int status);

typedef struct {
	long tv_sec;
	long tv_nsec;
} uv_timespec_t;

typedef struct {
	uint64_t st_dev;
	uint64_t st_mode;
	uint64_t st_nlink;
	uint64_t st_uid;
	uint64_t st_gid;
	uint64_t st_rdev;
	uint64_t st_ino;
	uint64_t st_size;
	uint64_t st_blksize;
	uint64_t st_blocks;
	uint64_t st_flags;
	uint64_t st_gen;
	uv_timespec_t st_atim;
	uv_timespec_t st_mtim;
	uv_timespec_t st_ctim;
	uv_timespec_t st_birthtim;
} uv_stat_t;

typedef void (*uv_fs_poll_cb)(uv_fs_poll_t* handle, int status, const uv_stat_t* prev, const uv_stat_t* curr);

// loop functions
uv_loop_t *uv_default_loop();
uv_loop_t* uv_loop_new(); // not documented; neither is uv_loop_delete
int uv_loop_init(uv_loop_t* loop);
int uv_loop_fork(uv_loop_t* loop);
int uv_loop_alive(const uv_loop_t *loop);
int uv_loop_close(uv_loop_t* loop);
uint64_t uv_backend_timeout(uv_loop_t* loop);
int uv_run(uv_loop_t *, uv_run_mode mode);
int uv_backend_fd(const uv_loop_t* loop);
// The narrative docs for the two time functions say 'const',
// but the header does not.
void uv_update_time(uv_loop_t* loop);
uint64_t uv_now(uv_loop_t* loop);
void uv_stop(uv_loop_t *);
void uv_walk(uv_loop_t *loop, uv_walk_cb walk_cb, void *arg);

// handle functions
// uv_handle_t is the base type for all libuv handle types.

void uv_ref(void *);
void uv_unref(void *);
int uv_has_ref(void *);
void uv_close(void *handle, uv_close_cb close_cb);
int uv_is_active(void *handle);
int uv_is_closing(void *handle);

// idle functions
// Idle handles will run the given callback once per loop iteration, right
// before the uv_prepare_t handles. Note: The notable difference with prepare
// handles is that when there are active idle handles, the loop will perform a
// zero timeout poll instead of blocking for i/o. Warning: Despite the name,
// idle handles will get their callbacks called on every loop iteration, not
// when the loop is actually "idle".
int uv_idle_init(uv_loop_t *, uv_idle_t *idle);
int uv_idle_start(uv_idle_t *idle, uv_idle_cb cb);
int uv_idle_stop(uv_idle_t *idle);

// prepare functions
// Prepare handles will run the given callback once per loop iteration, right
// before polling for i/o.
int uv_prepare_init(uv_loop_t *, uv_prepare_t *prepare);
int uv_prepare_start(uv_prepare_t *prepare, uv_prepare_cb cb);
int uv_prepare_stop(uv_prepare_t *prepare);

// check functions
// Check handles will run the given callback once per loop iteration, right
int uv_check_init(uv_loop_t *, uv_check_t *check);
int uv_check_start(uv_check_t *check, uv_check_cb cb);
int uv_check_stop(uv_check_t *check);

// async functions
// Async handles allow the user to "wakeup" the event loop and get a callback called from another thread.

int uv_async_init(uv_loop_t *, uv_async_t*, uv_async_cb);
int uv_async_send(uv_async_t*);

// timer functions
// Timer handles are used to schedule callbacks to be called in the future.
int uv_timer_init(uv_loop_t *, uv_timer_t *handle);
int uv_timer_start(uv_timer_t *handle, uv_timer_cb cb, uint64_t timeout, uint64_t repeat);
int uv_timer_stop(uv_timer_t *handle);
int uv_timer_again(uv_timer_t *handle);
void uv_timer_set_repeat(uv_timer_t *handle, uint64_t repeat);
uint64_t uv_timer_get_repeat(const uv_timer_t *handle);

// signal functions
// Signal handles implement Unix style signal handling on a per-event loop
// bases.
int uv_signal_init(uv_loop_t *loop, uv_signal_t *handle);
int uv_signal_start(uv_signal_t *handle, uv_signal_cb signal_cb, int signum);
int uv_signal_stop(uv_signal_t *handle);

// poll functions Poll handles are used to watch file descriptors for
// readability and writability, similar to the purpose of poll(2). It
// is not okay to have multiple active poll handles for the same
// socket, this can cause libuv to busyloop or otherwise malfunction.
//
// The purpose of poll handles is to enable integrating external
// libraries that rely on the event loop to signal it about the socket
// status changes, like c-ares or libssh2. Using uv_poll_t for any
// other purpose is not recommended; uv_tcp_t, uv_udp_t, etc. provide
// an implementation that is faster and more scalable than what can be
// achieved with uv_poll_t, especially on Windows.
//
// Note On windows only sockets can be polled with poll handles. On
// Unix any file descriptor that would be accepted by poll(2) can be
// used.
int uv_poll_init(uv_loop_t *loop, uv_poll_t *handle, int fd);

// Initialize the handle using a socket descriptor. On Unix this is
// identical to uv_poll_init(). On windows it takes a SOCKET handle;
// SOCKET handles are another name for HANDLE objects in win32, and
// those are defined as PVOID, even though they are not actually
// pointers (they're small integers). CPython and PyPy both return
// the SOCKET (as cast to an int) from the socket.fileno() method.
// libuv uses ``uv_os_sock_t`` for this type, which is defined as an
// int on unix.
int uv_poll_init_socket(uv_loop_t* loop, uv_poll_t* handle, GEVENT_UV_OS_SOCK_T socket);
int uv_poll_start(uv_poll_t *handle, int events, uv_poll_cb cb);
int uv_poll_stop(uv_poll_t *handle);

// FS Event handles allow the user to monitor a given path for
// changes, for example, if the file was renamed or there was a
// generic change in it. This handle uses the best backend for the job
// on each platform.
//
// Thereas also uv_fs_poll_t that uses stat for filesystems where
// the kernel event isn't available.
int uv_fs_event_init(uv_loop_t*, uv_fs_event_t*);
int uv_fs_event_start(uv_fs_event_t*, uv_fs_event_cb, const char* path, unsigned int flags);
int uv_fs_event_stop(uv_fs_event_t*);
int uv_fs_event_getpath(uv_fs_event_t*, char* buffer, size_t* size);

// FS Poll handles allow the user to monitor a given path for changes.
// Unlike uv_fs_event_t, fs poll handles use stat to detect when a
// file has changed so they can work on file systems where fs event
// handles can't.
//
// This is a closer match to libev.
int uv_fs_poll_init(void*, void*);
int uv_fs_poll_start(void*, uv_fs_poll_cb, const char* path, unsigned int);
int uv_fs_poll_stop(void*);

// CPU Info
unsigned int uv_available_parallelism(void);
/* We don't have uv_cpu_info medeled
int uv_cpu_info(uv_cpu_info_t** cpu_infos, int* count);
void uv_free_cpu_info(uv_cpu_info_t* cpu_infos, int count);
*/

// DNS
/* We don't have sockaddr modeled.
int uv_ip4_name(const struct sockaddr_in* src, char* dst, size_t size);
int uv_ip6_name(const struct sockaddr_in6* src, char* dst, size_t size);
int uv_ip_name(const struct sockaddr* src, char* dst, size_t size);

int uv_inet_ntop(int af, const void* src, char* dst, size_t size);
int uv_inet_pton(int af, const char* src, void* dst);
*/

/* Standard library */
void* memset(void *b, int c, size_t len);


/* gevent callbacks */
// Implemented in Python code as 'def_extern'. In the case of poll callbacks and fs
// callbacks, if *status* is less than 0, it will be passed in the revents
// field. In cases of no extra arguments, revents will be 0.
// These will be created as static functions at the end of the
// _source.c and must be pre-declared at the top of that file if we
// call them
typedef void* GeventWatcherObject;
extern "Python" {
    // Standard gevent._ffi.loop callbacks.
    int python_callback(GeventWatcherObject handle, int revents);
    void python_handle_error(GeventWatcherObject handle, int revents);
    void python_stop(GeventWatcherObject handle);

    void python_check_callback(uv_check_t* handle);
    void python_prepare_callback(uv_prepare_t* handle);
    void python_timer0_callback(uv_check_t* handle);

    // libuv specific callback
    void _uv_close_callback(uv_handle_t* handle);
    void python_sigchld_callback(uv_signal_t* handle, int signum);
    void python_queue_callback(uv_handle_t* handle, int revents);
}

static void _gevent_signal_callback1(uv_signal_t* handle, int arg);
static void _gevent_async_callback0(uv_async_t* handle);
static void _gevent_prepare_callback0(uv_prepare_t* handle);
static void _gevent_timer_callback0(uv_timer_t* handle);
static void _gevent_check_callback0(uv_check_t* handle);
static void _gevent_idle_callback0(uv_idle_t* handle);
static void _gevent_poll_callback2(uv_poll_t* handle, int status, int events);
static void _gevent_fs_event_callback3(uv_fs_event_t* handle, const char* filename, int events, int status);

typedef struct _gevent_fs_poll_s {
	uv_fs_poll_t handle;
	uv_stat_t curr;
	uv_stat_t prev;
} gevent_fs_poll_t;

static void _gevent_fs_poll_callback3(uv_fs_poll_t* handle, int status, const uv_stat_t* prev, const uv_stat_t* curr);

static void gevent_uv_walk_callback_close(uv_handle_t* handle, void* arg);
static void gevent_close_all_handles(uv_loop_t* loop);

/* gevent utility functions */
static void gevent_zero_timer(uv_timer_t* handle);
static void gevent_zero_prepare(uv_prepare_t* handle);
static void gevent_zero_check(uv_check_t* handle);
static void gevent_zero_loop(uv_loop_t* handle);
static void gevent_set_uv_alloc();
static void gevent_test_setup();
