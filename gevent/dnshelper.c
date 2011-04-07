#include "Python.h"

#include "ares__close_sockets.c"
#include "ares_data.c"
#include "ares_destroy.c"
#include "ares_expand_name.c"
#include "ares_free_hostent.c"
#include "ares_free_string.c"
#include "ares_gethostbyaddr.c"
#include "ares_gethostbyname.c"
#include "ares__get_hostent.c"
#include "ares_getnameinfo.c"
#include "ares_init.c"
#include "ares_library_init.c"
#include "ares_llist.c"
#include "ares_mkquery.c"
#include "ares_nowarn.c"
#include "ares_options.c"
#include "ares_parse_aaaa_reply.c"
#include "ares_parse_a_reply.c"
#include "ares_parse_ptr_reply.c"
#include "ares_process.c"
#include "ares_query.c"
#include "ares__read_line.c"
#include "ares_search.c"
#include "ares_send.c"
#include "ares_strerror.c"
//#include "ares_timeout.c"
#include "ares__timeval.c"
//#include "ares_version.c"
#include "bitncmp.c"
#include "inet_net_pton.c"
#include "inet_ntop.c"

#ifdef _WIN32
#include "windows_port.c"
#endif


static PyObject* _socket_error = 0;
static PyObject* _socket_gaierror = 0;

static inline PyObject* get_socket_object(PyObject** pobject, const char* name, int incref)
{
    if (!*pobject) {
        PyObject* _socket;
        _socket = PyImport_ImportModuleNoBlock("_socket");
        if (_socket) {
            *pobject = PyObject_GetAttrString(_socket, name);
            if (!*pobject) {
                PyErr_WriteUnraisable(Py_None);
            }
            Py_DECREF(_socket);
        }
        else {
            PyErr_WriteUnraisable(Py_None);
        }
        if (!*pobject) {
            *pobject = PyExc_IOError;
        }
    }
    if (incref)
        Py_INCREF(*pobject);
    return *pobject;
}

static inline PyObject* get_socket_error() { return get_socket_object(&_socket_error, "error", 1); }
static inline PyObject* get_socket_gaierror() { return get_socket_object(&_socket_gaierror, "gaierror", 1); }

static int gevent_append_addr(PyObject* list, int family, void* src, char* tmpbuf, size_t tmpsize) {
    int status = -1;
    PyObject* tmp;
    if (ares_inet_ntop(family, src, tmpbuf, tmpsize)) {
        tmp = PyString_FromString(tmpbuf);
        if (tmp) {
            status = PyList_Append(list, tmp);
            Py_DECREF(tmp);
        }
    }
    return status;
}


static PyObject*
parse_h_aliases(struct hostent *h)
{
    char **pch;
    PyObject *result = NULL;
    PyObject *tmp;

    result = PyList_New(0);

    if (result && h->h_aliases) {
        for (pch = h->h_aliases; *pch != NULL; pch++) {
            if (*pch != h->h_name && strcmp(*pch, h->h_name)) {
                int status;
                tmp = PyString_FromString(*pch);
                if (tmp == NULL) {
                    break;
                }

                status = PyList_Append(result, tmp);
                Py_DECREF(tmp);

                if (status) {
                    break;
                }
            }
        }
    }

    return result;
}


static PyObject *
parse_h_addr_list(struct hostent *h)
{
    char **pch;
    PyObject *result = NULL;
    PyObject *tmp;

    result = PyList_New(0);

    if (result) {
        switch (h->h_addrtype) {
            case AF_INET:
            {
                char tmpbuf[sizeof "255.255.255.255"];
                for (pch = h->h_addr_list; *pch != NULL; pch++) {
                    if (gevent_append_addr(result, AF_INET, *pch, tmpbuf, sizeof(tmpbuf))) {
                        break;
                    }
                }
                break;
            }
            case AF_INET6:
            {
                char tmpbuf[sizeof("ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255")];
                for (pch = h->h_addr_list; *pch != NULL; pch++) {
                    if (gevent_append_addr(result, AF_INET6, *pch, tmpbuf, sizeof(tmpbuf))) {
                        break;
                    }
                }
                break;
            }
            default:
                PyErr_SetString(get_socket_object(&_socket_error, "error", 0), "unsupported address family");
                Py_DECREF(result);
                result = NULL;
        }
    }

    return result;
}


static inline int gevent_make_sockaddr(char* hostp, int port, int flowinfo, int scope_id, struct sockaddr_in6* sa6) {
    if ( ares_inet_pton(AF_INET, hostp, &((struct sockaddr_in*)sa6)->sin_addr.s_addr) > 0 ) {
        ((struct sockaddr_in*)sa6)->sin_family = AF_INET;
        ((struct sockaddr_in*)sa6)->sin_port = htons(port);
        return sizeof(struct sockaddr_in);
    }
    else if ( ares_inet_pton(AF_INET6, hostp, &sa6->sin6_addr.s6_addr) > 0 ) {
        sa6->sin6_family = AF_INET6;
        sa6->sin6_port = htons(port);
        sa6->sin6_flowinfo = flowinfo;
        sa6->sin6_scope_id = scope_id;
        return sizeof(struct sockaddr_in6);
    }
    return -1;
}
