#if defined(LIBEV_EMBED)
#include "ev.c"
#else
#include "ev.h"

#if EV_CHILD_ENABLE
#include <signal.h>
#endif

#endif

#if EV_CHILD_ENABLE

static struct sigaction libev_sigchld;
static int sigchld_state = 0;

static struct ev_loop* gevent_ev_default_loop(unsigned int flags)
{
    if (sigchld_state)
        return ev_default_loop(flags);
    struct ev_loop* result;
    struct sigaction tmp;
    sigaction(SIGCHLD, NULL, &tmp);
    result = ev_default_loop(flags);
    // XXX what if SIGCHLD received there?
    sigaction(SIGCHLD, &tmp, &libev_sigchld);
    sigchld_state = 1;
    return result;
}


static void gevent_install_sigchld_handler(void) {
    if (sigchld_state == 1) {
        sigaction(SIGCHLD, &libev_sigchld, NULL);
        sigchld_state = 2;
    }
}

#else

#define gevent_ev_default_loop ev_default_loop
static void gevent_install_sigchld_handler(void) { }

#endif
