/* Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details. */

#ifdef WIN32
#include "winsock2.h" // for timeval
#endif

#include "sys/queue.h"

#ifdef USE_LIBEVENT_2

#include "event2/event.h"
#include "event2/event_struct.h"
#include "event2/event_compat.h"
#include "event2/http.h"
#include "event2/http_compat.h"
#include "event2/http_struct.h"
#include "event2/buffer.h"
#include "event2/buffer_compat.h"
#include "event2/dns.h"
#include "event2/dns_compat.h"

#define EVBUFFER_DRAIN evbuffer_drain
#define EVHTTP_SET_CB  evhttp_set_cb

#elif USE_LIBEVENT_1

#include "event.h"
#include "evhttp.h"
#include "evdns.h"

/* compatibility */

#define evbuffer_get_length EVBUFFER_LENGTH
#define evbuffer_pullup(BUF, SIZE) EVBUFFER_DATA(BUF)

#define TAILQ_FIRST(head) ((head)->tqh_first)
#define	TAILQ_NEXT(elm, field) ((elm)->field.tqe_next)

/* functions that return int in libeven2 but void in libevent1 */
#define EVBUFFER_DRAIN(A, B) (evbuffer_drain((A), (B)), 0)
#define EVHTTP_SET_CB(A, B, C, D) (evhttp_set_cb((A), (B), (C), (D)), 0)

#else

#error "Please define either USE_LIBEVENT_1 or USE_LIBEVENT_2"

#endif

#define TAILQ_GET_NEXT(X) TAILQ_NEXT((X), next)

extern void *current_base;

