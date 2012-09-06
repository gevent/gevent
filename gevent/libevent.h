/* Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details. */

#ifdef WIN32
#include "winsock2.h" // for timeval
#endif

#include "sys/queue.h"

#include "event.h"

#if defined(_EVENT_NUMERIC_VERSION) && _EVENT_NUMERIC_VERSION >= 0x2000000

#if _EVENT_NUMERIC_VERSION >= 0x02000900
#define LIBEVENT_HTTP_MODERN
#endif

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
#define EVBUFFER_PULLUP(BUF, SIZE) evbuffer_pullup(BUF, SIZE)

#if _EVENT_NUMERIC_VERSION >= 0x02000500
#define current_base event_global_current_base_
#endif

#else

#include "evhttp.h"
#include "evdns.h"

/* compatibility */

#define evbuffer_get_length EVBUFFER_LENGTH
#define EVBUFFER_PULLUP(BUF, SIZE) EVBUFFER_DATA(BUF)

#define TAILQ_FIRST(head) ((head)->tqh_first)
#define	TAILQ_NEXT(elm, field) ((elm)->field.tqe_next)

/* functions that return int in libeven2 but void in libevent1 */
#define EVBUFFER_DRAIN(A, B) (evbuffer_drain((A), (B)), 0)
#define EVHTTP_SET_CB(A, B, C, D) (evhttp_set_cb((A), (B), (C), (D)), 0)

#ifndef EVHTTP_REQ_PUT
#define EVHTTP_REQ_PUT -1
#endif

#ifndef EVHTTP_REQ_DELETE
#define EVHTTP_REQ_DELETE -1
#endif

#ifndef EVHTTP_REQ_OPTIONS
#define EVHTTP_REQ_OPTIONS -1
#endif

#ifndef EVHTTP_REQ_TRACE
#define EVHTTP_REQ_TRACE -1
#endif

#ifndef EVHTTP_REQ_CONNECT
#define EVHTTP_REQ_CONNECT -1
#endif

#ifndef EVHTTP_REQ_PATCH
#define EVHTTP_REQ_PATCH -1
#endif

#endif

#define TAILQ_GET_NEXT(X) TAILQ_NEXT((X), next)

extern void *current_base;

