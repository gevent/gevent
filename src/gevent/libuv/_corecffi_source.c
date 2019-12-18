#include <string.h>
#include <assert.h>
#include "uv.h"

typedef void* GeventWatcherObject;
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused"
#pragma clang diagnostic ignored "-Wunused-parameter"
#pragma clang diagnostic ignored "-Wundefined-internal"
#endif

static int python_callback(GeventWatcherObject handle, int revents);
static void python_queue_callback(uv_handle_t* watcher_ptr, int revents);
static void python_handle_error(GeventWatcherObject handle, int revents);
static void python_stop(GeventWatcherObject handle);

static void _gevent_generic_callback1(uv_handle_t* watcher, int arg)
{
    python_queue_callback(watcher, arg);
}

static void _gevent_generic_callback0(uv_handle_t* handle)
{
    _gevent_generic_callback1(handle, 0);
}

static void _gevent_async_callback0(uv_async_t* handle)
{
    _gevent_generic_callback0((uv_handle_t*)handle);
}

static void _gevent_timer_callback0(uv_timer_t* handle)
{
    _gevent_generic_callback0((uv_handle_t*)handle);
}

static void _gevent_prepare_callback0(uv_prepare_t* handle)
{
    _gevent_generic_callback0((uv_handle_t*)handle);
}

static void _gevent_check_callback0(uv_check_t* handle)
{
    _gevent_generic_callback0((uv_handle_t*)handle);
}

static void _gevent_idle_callback0(uv_idle_t* handle)
{
    _gevent_generic_callback0((uv_handle_t*)handle);
}

static void _gevent_signal_callback1(uv_signal_t* handle, int signum)
{
    _gevent_generic_callback1((uv_handle_t*)handle, signum);
}


static void _gevent_poll_callback2(void* handle, int status, int events)
{
    _gevent_generic_callback1(handle, status < 0 ? status : events);
}

static void _gevent_fs_event_callback3(void* handle, const char* filename, int events, int status)
{
    _gevent_generic_callback1(handle, status < 0 ? status : events);
}


typedef struct _gevent_fs_poll_s {
    uv_fs_poll_t handle;
    uv_stat_t curr;
    uv_stat_t prev;
} gevent_fs_poll_t;

static void _gevent_fs_poll_callback3(void* handlep, int status, const uv_stat_t* prev, const uv_stat_t* curr)
{
    // stat pointers are valid for this callback only.
    // if given, copy them into our structure, where they can be reached
    // from python, just like libev's watcher does, before calling
    // the callback.

    // The callback is invoked with status < 0 if path does not exist
    // or is inaccessible. The watcher is not stopped but your
    // callback is not called again until something changes (e.g. when
    // the file is created or the error reason changes).
    // In that case the fields will be 0 in curr/prev.


    gevent_fs_poll_t* handle = (gevent_fs_poll_t*)handlep;
    assert(status == 0);

    handle->curr = *curr;
    handle->prev = *prev;

    _gevent_generic_callback1((uv_handle_t*)handle, 0);
}

static void gevent_uv_walk_callback_close(uv_handle_t* handle, void* arg)
{
    if( handle && !uv_is_closing(handle) ) {
	uv_close(handle, NULL);
    }
}

static void gevent_close_all_handles(uv_loop_t* loop)
{
    if (loop) {
	uv_walk(loop, gevent_uv_walk_callback_close, NULL);
    }
}

static void gevent_zero_timer(uv_timer_t* handle)
{
    memset(handle, 0, sizeof(uv_timer_t));
}

static void gevent_zero_check(uv_check_t* handle)
{
    memset(handle, 0, sizeof(uv_check_t));
}

static void gevent_zero_prepare(uv_prepare_t* handle)
{
    memset(handle, 0, sizeof(uv_prepare_t));
}

static void gevent_zero_loop(uv_loop_t* handle)
{
    memset(handle, 0, sizeof(uv_loop_t));
}

#ifdef __clang__
#pragma clang diagnostic pop
#endif

/* Local Variables: */
/* flycheck-clang-include-path: ("../../../deps/libuv/include") */
/* End: */
