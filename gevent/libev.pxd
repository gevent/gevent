cdef extern from "libev_vfd.h":
    long vfd_get(int)
    int vfd_open(long) except -1
    void vfd_free(int)

cdef extern from "libev.h":
    int EV_MINPRI
    int EV_MAXPRI

    int EV_VERSION_MAJOR
    int EV_VERSION_MINOR

    int EV_UNDEF
    int EV_NONE
    int EV_READ
    int EV_WRITE
    int EV__IOFDSET
    int EV_TIMER
    int EV_PERIODIC
    int EV_SIGNAL
    int EV_CHILD
    int EV_STAT
    int EV_IDLE
    int EV_PREPARE
    int EV_CHECK
    int EV_EMBED
    int EV_FORK
    int EV_CLEANUP
    int EV_ASYNC
    int EV_CUSTOM
    int EV_ERROR

    int EVFLAG_AUTO
    int EVFLAG_NOENV
    int EVFLAG_FORKCHECK
    int EVFLAG_NOINOTIFY
    int EVFLAG_SIGNALFD
    int EVFLAG_NOSIGMASK

    int EVBACKEND_SELECT
    int EVBACKEND_POLL
    int EVBACKEND_EPOLL
    int EVBACKEND_KQUEUE
    int EVBACKEND_DEVPOLL
    int EVBACKEND_PORT
    int EVBACKEND_IOCP
    int EVBACKEND_ALL
    int EVBACKEND_MASK

    int EVRUN_NOWAIT
    int EVRUN_ONCE

    int EVBREAK_CANCEL
    int EVBREAK_ONE
    int EVBREAK_ALL

    struct ev_loop:
        int activecnt
        int backend_fd
        int fdchangecnt
        int timercnt

    struct ev_io:
        int fd
        int events

    struct ev_timer:
        double at

    struct ev_signal:
        pass

    struct ev_idle:
        pass

    struct ev_prepare:
        pass

    struct ev_fork:
        pass

    struct ev_async:
        pass

    struct ev_child:
        int pid
        int rpid
        int rstatus

    int ev_version_major()
    int ev_version_minor()

    unsigned int ev_supported_backends()
    unsigned int ev_recommended_backends()
    unsigned int ev_embeddable_backends()

    double ev_time()
    void ev_set_syserr_cb(void *)

    int ev_priority(void*)
    void ev_set_priority(void*, int)

    int ev_is_pending(void*)
    int ev_is_active(void*)
    void ev_io_init(ev_io*, void* callback, int fd, int events)
    void ev_io_start(ev_loop*, ev_io*)
    void ev_io_stop(ev_loop*, ev_io*)
    void ev_feed_event(ev_loop*, void*, int)

    void ev_timer_init(ev_timer*, void* callback, double, double)
    void ev_timer_start(ev_loop*, ev_timer*)
    void ev_timer_stop(ev_loop*, ev_timer*)
    void ev_timer_again(ev_loop*, ev_timer*)

    void ev_signal_init(ev_signal*, void* callback, int)
    void ev_signal_start(ev_loop*, ev_signal*)
    void ev_signal_stop(ev_loop*, ev_signal*)

    void ev_idle_init(ev_idle*, void* callback)
    void ev_idle_start(ev_loop*, ev_idle*)
    void ev_idle_stop(ev_loop*, ev_idle*)

    void ev_prepare_init(ev_prepare*, void* callback)
    void ev_prepare_start(ev_loop*, ev_prepare*)
    void ev_prepare_stop(ev_loop*, ev_prepare*)

    void ev_fork_init(ev_fork*, void* callback)
    void ev_fork_start(ev_loop*, ev_fork*)
    void ev_fork_stop(ev_loop*, ev_fork*)

    void ev_async_init(ev_async*, void* callback)
    void ev_async_start(ev_loop*, ev_async*)
    void ev_async_stop(ev_loop*, ev_async*)

    void ev_child_init(ev_child*, void* callback, int, int)
    void ev_child_start(ev_loop*, ev_child*)
    void ev_child_stop(ev_loop*, ev_child*)

    ev_loop* ev_default_loop(unsigned int flags)
    ev_loop* ev_loop_new(unsigned int flags)
    void ev_loop_destroy(ev_loop*)
    void ev_loop_fork(ev_loop*)
    int ev_is_default_loop(ev_loop*)
    unsigned int ev_iteration(ev_loop*)
    unsigned int ev_depth(ev_loop*)
    unsigned int ev_backend(ev_loop*)
    void ev_verify(ev_loop*)
    void ev_run(ev_loop*, int flags) nogil

    double ev_now(ev_loop*)
    void ev_now_update(ev_loop*)

    void ev_ref(ev_loop*)
    void ev_unref(ev_loop*)
    void ev_break(ev_loop*, int)
