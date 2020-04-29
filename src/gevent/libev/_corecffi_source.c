/* passed to the real C compiler */
#ifndef LIBEV_EMBED
/* We're normally used to embed libev, assume that */
/* When this is defined, libev.h includes ev.c */
#define LIBEV_EMBED 1
#endif

#ifdef _WIN32
#define EV_STANDALONE 1
#include "libev_vfd.h"
#endif


#include "libev.h"

static void
_gevent_noop(struct ev_loop *_loop, struct ev_timer *w, int revents) { }

void (*gevent_noop)(struct ev_loop *, struct ev_timer *, int) = &_gevent_noop;

static int python_callback(void* handle, int revents);
static void python_handle_error(void* handle, int revents);
static void python_stop(void* handle);

static void _gevent_generic_callback(struct ev_loop* loop,
				     struct ev_watcher* watcher,
				     int revents)
{
    void* handle = watcher->data;
    int cb_result = python_callback(handle, revents);
    switch(cb_result) {
        case -1:
            // in case of exception, call self.loop.handle_error;
            // this function is also responsible for stopping the watcher
            // and allowing memory to be freed
            python_handle_error(handle, revents);
        break;
        case 1:
            // Code to stop the event. Note that if python_callback
            // has disposed of the last reference to the handle,
            // `watcher` could now be invalid/disposed memory!
            if (!ev_is_active(watcher)) {
                python_stop(handle);
            }
        break;
        case 2:
            // watcher is already stopped and dead, nothing to do.
        break;
        default:
            fprintf(stderr,
                    "WARNING: gevent: Unexpected return value %d from Python callback "
                    "for watcher %p and handle %p\n",
                    cb_result,
                    watcher, handle);
            // XXX: Possible leaking of resources here? Should we be
            // closing the watcher?
    }
}

static void gevent_zero_timer(struct ev_timer* handle)
{
	memset(handle, 0, sizeof(struct ev_timer));
}

static void gevent_zero_check(struct ev_check* handle)
{
	memset(handle, 0, sizeof(struct ev_check));
}

static void gevent_zero_prepare(struct ev_prepare* handle)
{
	memset(handle, 0, sizeof(struct ev_prepare));
}

#include "_ffi/alloc.c"

static void gevent_set_ev_alloc()
{
    void* (*ptr)(void*, long);
    ptr = (void*(*)(void*, long))&gevent_realloc;
    ev_set_allocator(ptr);
}

#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunreachable-code"
#endif
