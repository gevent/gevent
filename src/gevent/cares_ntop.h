#ifdef CARES_EMBED
#include "ares_setup.h"
#include "ares.h"
#else
#include <arpa/inet.h>
#define ares_inet_ntop(w,x,y,z) inet_ntop(w,x,y,z)
#endif
