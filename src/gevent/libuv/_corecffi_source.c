#include <string.h>
#include <assert.h>
#include "uv.h"
#include "Python.h"

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

    handle->curr = *curr;
    handle->prev = *prev;

    _gevent_generic_callback1((uv_handle_t*)handle, 0);
}

static void gevent_uv_walk_callback_close(uv_handle_t* handle, void* arg)
{
    if( handle && !uv_is_closing(handle) ) {
        uv_close(handle, NULL);
        handle->data = NULL;
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

/***
 * Allocation functions
 */

#include "_ffi/alloc.c"

static void* _gevent_uv_malloc(size_t size)
{
    return gevent_realloc(NULL, size);
}

static void* _gevent_uv_realloc(void* ptr, size_t size)
{
    return gevent_realloc(ptr, size);
}

static void _gevent_uv_free(void* ptr)
{
    gevent_realloc(ptr, 0);
}

static void* _gevent_uv_calloc(size_t count, size_t size)
{
    // We assume no overflows. Not using PyObject_Calloc because
    // it's not available prior to 3.5 and isn't in PyPy.
    void* result;
    result = _gevent_uv_malloc(count * size);
    if(result) {
        memset(result, 0, count * size);
    }
    return result;
}

static void gevent_set_uv_alloc()
{
    uv_replace_allocator(_gevent_uv_malloc,
                         _gevent_uv_realloc,
                         _gevent_uv_calloc,
                         _gevent_uv_free);
}

/***
 * Utility Functions
 */
#ifdef __APPLE__
#include <mach/mach.h>
#include <mach/mach_time.h>
#include <pthread.h>

// based on code from libuv
static void gevent_move_pthread_to_realtime_scheduling_class(pthread_t pthread)
{
    mach_timebase_info_data_t timebase_info;
    mach_timebase_info(&timebase_info);

    const uint64_t NANOS_PER_MSEC = 1000000ULL;
    double clock2abs = ((double)timebase_info.denom / (double)timebase_info.numer) * NANOS_PER_MSEC;

    thread_time_constraint_policy_data_t policy;
    policy.period = 0;
    policy.computation = (uint32_t)(5 * clock2abs); // 5 ms of work
    policy.constraint = (uint32_t)(10 * clock2abs);
    policy.preemptible = FALSE;

    int kr = thread_policy_set(
        pthread_mach_thread_np(pthread),
        THREAD_TIME_CONSTRAINT_POLICY,
        (thread_policy_t)&policy,
        THREAD_TIME_CONSTRAINT_POLICY_COUNT);

    if (kr != KERN_SUCCESS) {
        mach_error("thread_policy_set:", kr);
        exit(1);
    }
}

static void gevent_test_setup()
{
    gevent_move_pthread_to_realtime_scheduling_class(pthread_self());
}
#else
static void gevent_test_setup() {}
#endif


#ifdef __clang__
#pragma clang diagnostic pop
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunreachable-code"
#endif
