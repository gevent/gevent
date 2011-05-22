#ifdef CARES_EMBED
#include "ares_setup.h"
#include "inet_net_pton.h"
#else
#include <arpa/inet.h>
#define ares_inet_pton(x,y,z) inet_pton(x,y,z)
#define ares_inet_net_pton(w,x,y,z) inet_net_pton(w,x,y,z)
#endif
