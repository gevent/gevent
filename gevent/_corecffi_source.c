// passed to the real C compiler
#define LIBEV_EMBED 1

#ifdef _WIN32
#define EV_STANDALONE 1
#include "libev_vfd.h"
#endif


#include "libev.h"

static void
_gevent_noop(struct ev_loop *_loop, struct ev_timer *w, int revents) { }

void (*gevent_noop)(struct ev_loop *, struct ev_timer *, int) = &_gevent_noop;
static int (*python_callback)(void* handle, int revents);
static void (*python_handle_error)(void* handle, int revents);
static void (*python_stop)(void* handle);

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
        case 0:
            // Code to stop the event. Note that if python_callback
            // has disposed of the last reference to the handle,
            // `watcher` could now be invalid/disposed memory!
            if (!ev_is_active(watcher)) {
                python_stop(handle);
            }
        break;
        default:
            assert(cb_result == 1);
            // watcher is already stopped and dead, nothing to do.
    }
}
