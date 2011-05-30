#if defined(EV_STANDALONE)
#include "ev.c"
#else
#include "ev.h"
#endif

#if (!EV_CHILD_ENABLE)
/* When ev_child is not available (Windows), we should not define gevent.core.child and gevent.core.loop.child().
 * Temporarily defining no-op functions since there's no easy way to do optional methods with Cython. */
void ev_child_start(void*, void*);
void ev_child_start(void* a, void* b) {}
void ev_child_stop(void*, void*);
void ev_child_stop(void* a, void* b) {}
#endif

