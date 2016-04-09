#include "uv.h"

static int (*python_callback)(void* handle, int revents);
static void (*python_handle_error)(void* handle, int revents);
static void (*python_stop)(void* handle);

static void _gevent_noop(void*handle) {}

static void (*gevent_noop)(void* handle) = &_gevent_noop;

static void _gevent_generic_callback1(void* vwatcher, int arg)
{
	uv_handle_t* watcher = (uv_handle_t*)vwatcher;
    void* handle = watcher->data;
    int cb_result = python_callback(handle, arg);
    switch(cb_result) {
        case -1:
            // in case of exception, call self.loop.handle_error;
            // this function is also responsible for stopping the watcher
            // and allowing memory to be freed
            python_handle_error(handle, arg);
        break;
        case 0:
            // Code to stop the event. Note that if python_callback
            // has disposed of the last reference to the handle,
            // `watcher` could now be invalid/disposed memory!
            if (!uv_is_active(watcher)) {
                python_stop(handle);
            }
        break;
        default:
            assert(cb_result == 1);
            // watcher is already stopped and dead, nothing to do.
    }
}


static void _gevent_generic_callback0(void* handle)
{
	_gevent_generic_callback1(handle, 0);
}

static void _gevent_poll_callback2(void* handle, int status, int events)
{
	_gevent_generic_callback1(handle, status < 0 ? status : events);
}

static void _gevent_fs_event_callback3(void* handle, const char* filename, int events, int status)
{
	_gevent_generic_callback1(handle, status < 0 ? status : events);
}
/*
typedef struct {
	uv_fs_poll_t handle;
	uv_stat_t curr;
	uv_stat_t prev;
} gevent_fs_poll_t;
*/

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
