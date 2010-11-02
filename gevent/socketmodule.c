/* XXX Remove unnecessary #defines and #includes
 * XXX MAke sure we don't export symbols we don't want to export (check with ldd) */

/* This code is lifted from Python 2.7 */
#include "Python.h"

/* XXX This is a terrible mess of platform-dependent preprocessor hacks.
   I hope some day someone can clean this up please... */

/* Hacks for gethostbyname_r().  On some non-Linux platforms, the configure
   script doesn't get this right, so we hardcode some platform checks below.
   On the other hand, not all Linux versions agree, so there the settings
   computed by the configure script are needed! */

#ifndef linux
# undef HAVE_GETHOSTBYNAME_R_3_ARG
# undef HAVE_GETHOSTBYNAME_R_5_ARG
# undef HAVE_GETHOSTBYNAME_R_6_ARG
#endif

#ifndef WITH_THREAD
# undef HAVE_GETHOSTBYNAME_R
#endif

#ifdef HAVE_GETHOSTBYNAME_R
# if defined(_AIX) || defined(__osf__)
#  define HAVE_GETHOSTBYNAME_R_3_ARG
# elif defined(__sun) || defined(__sgi)
#  define HAVE_GETHOSTBYNAME_R_5_ARG
# elif defined(linux)
/* Rely on the configure script */
# else
#  undef HAVE_GETHOSTBYNAME_R
# endif
#endif

#if !defined(HAVE_GETHOSTBYNAME_R) && defined(WITH_THREAD) && \
    !defined(MS_WINDOWS)
# define USE_GETHOSTBYNAME_LOCK
#endif

/* To use __FreeBSD_version */
#ifdef HAVE_SYS_PARAM_H
#include <sys/param.h>
#endif
/* On systems on which getaddrinfo() is believed to not be thread-safe,
   (this includes the getaddrinfo emulation) protect access with a lock. */
#if defined(WITH_THREAD) && (defined(__APPLE__) || \
    (defined(__FreeBSD__) && __FreeBSD_version+0 < 503000) || \
    defined(__OpenBSD__) || defined(__NetBSD__) || \
    defined(__VMS) || !defined(HAVE_GETADDRINFO))
#define USE_GETADDRINFO_LOCK
#endif

#ifdef USE_GETADDRINFO_LOCK
#define ACQUIRE_GETADDRINFO_LOCK PyThread_acquire_lock(netdb_lock, 1);
#define RELEASE_GETADDRINFO_LOCK PyThread_release_lock(netdb_lock);
#else
#define ACQUIRE_GETADDRINFO_LOCK
#define RELEASE_GETADDRINFO_LOCK
#endif

#if defined(USE_GETHOSTBYNAME_LOCK) || defined(USE_GETADDRINFO_LOCK)
# include "pythread.h"
#endif

#if defined(PYCC_VACPP)
# include <types.h>
# include <io.h>
# include <sys/ioctl.h>
# include <utils.h>
# include <ctype.h>
#endif

#if defined(__VMS)
#  include <ioctl.h>
#endif

#if defined(PYOS_OS2)
# define  INCL_DOS
# define  INCL_DOSERRORS
# define  INCL_NOPMAPI
# include <os2.h>
#endif

#if defined(__sgi) && _COMPILER_VERSION>700 && !_SGIAPI
/* make sure that the reentrant (gethostbyaddr_r etc)
   functions are declared correctly if compiling with
   MIPSPro 7.x in ANSI C mode (default) */

/* XXX Using _SGIAPI is the wrong thing,
   but I don't know what the right thing is. */
#undef _SGIAPI /* to avoid warning */
#define _SGIAPI 1

#undef _XOPEN_SOURCE
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#ifdef _SS_ALIGNSIZE
#define HAVE_GETADDRINFO 1
#define HAVE_GETNAMEINFO 1
#endif

#define HAVE_INET_PTON
#include <netdb.h>
#endif

/* Irix 6.5 fails to define this variable at all. This is needed
   for both GCC and SGI's compiler. I'd say that the SGI headers
   are just busted. Same thing for Solaris. */
#if (defined(__sgi) || defined(sun)) && !defined(INET_ADDRSTRLEN)
#define INET_ADDRSTRLEN 16
#endif

/* Generic includes */
#ifdef HAVE_SYS_TYPES_H
#include <sys/types.h>
#endif

/* Generic socket object definitions and includes */
#define PySocket_BUILDING_SOCKET
/* Socket module header file */

/* Includes needed for the sockaddr_* symbols below */
#ifndef MS_WINDOWS
#ifdef __VMS
#   include <socket.h>
# else
#   include <sys/socket.h>
# endif
# include <netinet/in.h>
# if !(defined(__BEOS__) || defined(__CYGWIN__) || (defined(PYOS_OS2) && defined(PYCC_VACPP)))
#  include <netinet/tcp.h>
# endif

#else /* MS_WINDOWS */
# include <winsock2.h>
# include <ws2tcpip.h>
/* VC6 is shipped with old platform headers, and does not have MSTcpIP.h
 * Separate SDKs have all the functions we want, but older ones don't have
 * any version information.
 * I use SIO_GET_MULTICAST_FILTER to detect a decent SDK.
 */
# ifdef SIO_GET_MULTICAST_FILTER
#  include <MSTcpIP.h> /* for SIO_RCVALL */
#  define HAVE_ADDRINFO
#  define HAVE_SOCKADDR_STORAGE
#  define HAVE_GETADDRINFO
#  define HAVE_GETNAMEINFO
#  define ENABLE_IPV6
# else
typedef int socklen_t;
# endif /* IPPROTO_IPV6 */
#endif /* MS_WINDOWS */

#ifdef HAVE_SYS_UN_H
# include <sys/un.h>
#else
# undef AF_UNIX
#endif

#ifdef HAVE_LINUX_NETLINK_H
# ifdef HAVE_ASM_TYPES_H
#  include <asm/types.h>
# endif
# include <linux/netlink.h>
#else
#  undef AF_NETLINK
#endif

#ifdef HAVE_BLUETOOTH_BLUETOOTH_H
#include <bluetooth/bluetooth.h>
#include <bluetooth/rfcomm.h>
#include <bluetooth/l2cap.h>
#include <bluetooth/sco.h>
#include <bluetooth/hci.h>
#endif

#ifdef HAVE_BLUETOOTH_H
#include <bluetooth.h>
#endif

#ifdef HAVE_NETPACKET_PACKET_H
# include <sys/ioctl.h>
# include <net/if.h>
# include <netpacket/packet.h>
#endif

#ifdef HAVE_LINUX_TIPC_H
# include <linux/tipc.h>
#endif

/* Python module and C API name */
#define PySocket_MODULE_NAME    "_socket"
#define PySocket_CAPI_NAME      "CAPI"
#define PySocket_CAPSULE_NAME  (PySocket_MODULE_NAME "." PySocket_CAPI_NAME)

/* Abstract the socket file descriptor type */
#ifdef MS_WINDOWS
typedef SOCKET SOCKET_T;
#       ifdef MS_WIN64
#               define SIZEOF_SOCKET_T 8
#       else
#               define SIZEOF_SOCKET_T 4
#       endif
#else
typedef int SOCKET_T;
#       define SIZEOF_SOCKET_T SIZEOF_INT
#endif

/* Socket address */
typedef union sock_addr {
    struct sockaddr_in in;
#ifdef AF_UNIX
    struct sockaddr_un un;
#endif
#ifdef AF_NETLINK
    struct sockaddr_nl nl;
#endif
#ifdef ENABLE_IPV6
    struct sockaddr_in6 in6;
    struct sockaddr_storage storage;
#endif
#ifdef HAVE_BLUETOOTH_BLUETOOTH_H
    struct sockaddr_l2 bt_l2;
    struct sockaddr_rc bt_rc;
    struct sockaddr_sco bt_sco;
    struct sockaddr_hci bt_hci;
#endif
#ifdef HAVE_NETPACKET_PACKET_H
    struct sockaddr_ll ll;
#endif
} sock_addr_t;



/* Addressing includes */

#ifndef MS_WINDOWS

/* Non-MS WINDOWS includes */
# include <netdb.h>

/* Headers needed for inet_ntoa() and inet_addr() */
# ifdef __BEOS__
#  include <net/netdb.h>
# elif defined(PYOS_OS2) && defined(PYCC_VACPP)
#  include <netdb.h>
typedef size_t socklen_t;
# else
#   include <arpa/inet.h>
# endif

# ifndef RISCOS
#  include <fcntl.h>
# else
#  include <sys/ioctl.h>
#  include <socklib.h>
#  define NO_DUP
int h_errno; /* not used */
#  define INET_ADDRSTRLEN 16
# endif

#else

/* MS_WINDOWS includes */
# ifdef HAVE_FCNTL_H
#  include <fcntl.h>
# endif

#endif

#include <stddef.h>

#ifndef offsetof
# define offsetof(type, member) ((size_t)(&((type *)0)->member))
#endif

#ifndef O_NONBLOCK
# define O_NONBLOCK O_NDELAY
#endif

#ifndef HAVE_INET_PTON
#if !defined(NTDDI_VERSION) || (NTDDI_VERSION < NTDDI_LONGHORN)
int inet_pton(int af, const char *src, void *dst);
const char *inet_ntop(int af, const void *src, char *dst, socklen_t size);
#endif
#endif

#ifdef __APPLE__
/* On OS X, getaddrinfo returns no error indication of lookup
   failure, so we must use the emulation instead of the libinfo
   implementation. Unfortunately, performing an autoconf test
   for this bug would require DNS access for the machine performing
   the configuration, which is not acceptable. Therefore, we
   determine the bug just by checking for __APPLE__. If this bug
   gets ever fixed, perhaps checking for sys/version.h would be
   appropriate, which is 10/0 on the system with the bug. */
#ifndef HAVE_GETNAMEINFO
/* This bug seems to be fixed in Jaguar. Ths easiest way I could
   Find to check for Jaguar is that it has getnameinfo(), which
   older releases don't have */
#undef HAVE_GETADDRINFO
#endif

#ifdef HAVE_INET_ATON
#define USE_INET_ATON_WEAKLINK
#endif

#endif


/* Convenience function to raise an error according to errno
   and return a NULL pointer from a function. */

static PyObject *
set_error(void)
{
#ifdef MS_WINDOWS
    int err_no = WSAGetLastError();
    /* PyErr_SetExcFromWindowsErr() invokes FormatMessage() which
       recognizes the error codes used by both GetLastError() and
       WSAGetLastError */
    if (err_no)
        return PyErr_SetExcFromWindowsErr(PyExc_IOError, err_no);
#endif

#if defined(PYOS_OS2) && !defined(PYCC_GCC)
    if (sock_errno() != NO_ERROR) {
        APIRET rc;
        ULONG  msglen;
        char outbuf[100];
        int myerrorcode = sock_errno();

        /* Retrieve socket-related error message from MPTN.MSG file */
        rc = DosGetMessage(NULL, 0, outbuf, sizeof(outbuf),
                           myerrorcode - SOCBASEERR + 26,
                           "mptn.msg",
                           &msglen);
        if (rc == NO_ERROR) {
            PyObject *v;

            /* OS/2 doesn't guarantee a terminator */
            outbuf[msglen] = '\0';
            if (strlen(outbuf) > 0) {
                /* If non-empty msg, trim CRLF */
                char *lastc = &outbuf[ strlen(outbuf)-1 ];
                while (lastc > outbuf &&
                       isspace(Py_CHARMASK(*lastc))) {
                    /* Trim trailing whitespace (CRLF) */
                    *lastc-- = '\0';
                }
            }
            v = Py_BuildValue("(is)", myerrorcode, outbuf);
            if (v != NULL) {
                PyErr_SetObject(PyExc_IOError, v);
                Py_DECREF(v);
            }
            return NULL;
        }
    }
#endif

#if defined(RISCOS)
    if (_inet_error.errnum != NULL) {
        PyObject *v;
        v = Py_BuildValue("(is)", errno, _inet_err());
        if (v != NULL) {
            PyErr_SetObject(PyExc_IOError, v);
            Py_DECREF(v);
        }
        return NULL;
    }
#endif

    return PyErr_SetFromErrno(PyExc_IOError);
}


char* get_gaierror(int error)
{
#ifdef HAVE_GAI_STRERROR
    return gai_strerror(error);
#else
    return "getaddrinfo failed";
#endif
}

static PyObject *
set_gaierror(int error)
{
    PyObject *v;

#ifdef EAI_SYSTEM
    /* EAI_SYSTEM is not available on Windows XP. */
    if (error == EAI_SYSTEM)
        return set_error();
#endif

#ifdef HAVE_GAI_STRERROR
    v = Py_BuildValue("(is)", error, gai_strerror(error));
#else
    v = Py_BuildValue("(is)", error, "getaddrinfo failed");
#endif
    if (v != NULL) {
        PyErr_SetObject(PyExc_IOError, v);
        Py_DECREF(v);
    }

    return NULL;
}


/* Create a string object representing an IP address.
   This is always a string of the form 'dd.dd.dd.dd' (with variable
   size numbers). */

static PyObject *
makeipaddr(struct sockaddr *addr, int addrlen)
{
    char buf[NI_MAXHOST];
    int error;

    error = getnameinfo(addr, addrlen, buf, sizeof(buf), NULL, 0,
        NI_NUMERICHOST);
    if (error) {
        set_gaierror(error);
        return NULL;
    }
    return PyString_FromString(buf);
}


/* Create an object representing the given socket address,
   suitable for passing it back to bind(), connect() etc.
   The family field of the sockaddr structure is inspected
   to determine what kind of address it really is. */

/*ARGSUSED*/
PyObject* makesockaddr(int sockfd, struct sockaddr *addr, int addrlen, int proto)
{
    if (addrlen == 0) {
        /* No address -- may be recvfrom() from known socket */
        Py_INCREF(Py_None);
        return Py_None;
    }

#ifdef __BEOS__
    /* XXX: BeOS version of accept() doesn't set family correctly */
    addr->sa_family = AF_INET;
#endif

    switch (addr->sa_family) {

    case AF_INET:
    {
        struct sockaddr_in *a;
        PyObject *addrobj = makeipaddr(addr, sizeof(*a));
        PyObject *ret = NULL;
        if (addrobj) {
            a = (struct sockaddr_in *)addr;
            ret = Py_BuildValue("Oi", addrobj, ntohs(a->sin_port));
            Py_DECREF(addrobj);
        }
        return ret;
    }

#if defined(AF_UNIX)
    case AF_UNIX:
    {
        struct sockaddr_un *a = (struct sockaddr_un *) addr;
#ifdef linux
        if (a->sun_path[0] == 0) {  /* Linux abstract namespace */
            addrlen -= offsetof(struct sockaddr_un, sun_path);
            return PyString_FromStringAndSize(a->sun_path,
                                              addrlen);
        }
        else
#endif /* linux */
        {
            /* regular NULL-terminated string */
            return PyString_FromString(a->sun_path);
        }
    }
#endif /* AF_UNIX */

#if defined(AF_NETLINK)
       case AF_NETLINK:
       {
           struct sockaddr_nl *a = (struct sockaddr_nl *) addr;
           return Py_BuildValue("II", a->nl_pid, a->nl_groups);
       }
#endif /* AF_NETLINK */

#ifdef ENABLE_IPV6
    case AF_INET6:
    {
        struct sockaddr_in6 *a;
        PyObject *addrobj = makeipaddr(addr, sizeof(*a));
        PyObject *ret = NULL;
        if (addrobj) {
            a = (struct sockaddr_in6 *)addr;
            ret = Py_BuildValue("Oiii",
                                addrobj,
                                ntohs(a->sin6_port),
                                a->sin6_flowinfo,
                                a->sin6_scope_id);
            Py_DECREF(addrobj);
        }
        return ret;
    }
#endif

#ifdef USE_BLUETOOTH
    case AF_BLUETOOTH:
        switch (proto) {

        case BTPROTO_L2CAP:
        {
            struct sockaddr_l2 *a = (struct sockaddr_l2 *) addr;
            PyObject *addrobj = makebdaddr(&_BT_L2_MEMB(a, bdaddr));
            PyObject *ret = NULL;
            if (addrobj) {
                ret = Py_BuildValue("Oi",
                                    addrobj,
                                    _BT_L2_MEMB(a, psm));
                Py_DECREF(addrobj);
            }
            return ret;
        }

        case BTPROTO_RFCOMM:
        {
            struct sockaddr_rc *a = (struct sockaddr_rc *) addr;
            PyObject *addrobj = makebdaddr(&_BT_RC_MEMB(a, bdaddr));
            PyObject *ret = NULL;
            if (addrobj) {
                ret = Py_BuildValue("Oi",
                                    addrobj,
                                    _BT_RC_MEMB(a, channel));
                Py_DECREF(addrobj);
            }
            return ret;
        }

        case BTPROTO_HCI:
        {
            struct sockaddr_hci *a = (struct sockaddr_hci *) addr;
            PyObject *ret = NULL;
            ret = Py_BuildValue("i", _BT_HCI_MEMB(a, dev));
            return ret;
        }

#if !defined(__FreeBSD__)
        case BTPROTO_SCO:
        {
            struct sockaddr_sco *a = (struct sockaddr_sco *) addr;
            return makebdaddr(&_BT_SCO_MEMB(a, bdaddr));
        }
#endif

        default:
            PyErr_SetString(PyExc_ValueError,
                            "Unknown Bluetooth protocol");
            return NULL;
        }
#endif

#ifdef HAVE_NETPACKET_PACKET_H
    case AF_PACKET:
    {
        struct sockaddr_ll *a = (struct sockaddr_ll *)addr;
        char *ifname = "";
        struct ifreq ifr;
        /* need to look up interface name give index */
        if (a->sll_ifindex) {
            ifr.ifr_ifindex = a->sll_ifindex;
            if (ioctl(sockfd, SIOCGIFNAME, &ifr) == 0)
                ifname = ifr.ifr_name;
        }
        return Py_BuildValue("shbhs#",
                             ifname,
                             ntohs(a->sll_protocol),
                             a->sll_pkttype,
                             a->sll_hatype,
                             a->sll_addr,
                             a->sll_halen);
    }
#endif

#ifdef HAVE_LINUX_TIPC_H
    case AF_TIPC:
    {
        struct sockaddr_tipc *a = (struct sockaddr_tipc *) addr;
        if (a->addrtype == TIPC_ADDR_NAMESEQ) {
            return Py_BuildValue("IIIII",
                            a->addrtype,
                            a->addr.nameseq.type,
                            a->addr.nameseq.lower,
                            a->addr.nameseq.upper,
                            a->scope);
        } else if (a->addrtype == TIPC_ADDR_NAME) {
            return Py_BuildValue("IIIII",
                            a->addrtype,
                            a->addr.name.name.type,
                            a->addr.name.name.instance,
                            a->addr.name.name.instance,
                            a->scope);
        } else if (a->addrtype == TIPC_ADDR_ID) {
            return Py_BuildValue("IIIII",
                            a->addrtype,
                            a->addr.id.node,
                            a->addr.id.ref,
                            0,
                            a->scope);
        } else {
            PyErr_SetString(PyExc_ValueError,
                            "Invalid address type");
            return NULL;
        }
    }
#endif

    /* More cases here... */

    default:
        /* If we don't know the address family, don't raise an
           exception -- return it as a tuple. */
        return Py_BuildValue("is#",
                             addr->sa_family,
                             addr->sa_data,
                             sizeof(addr->sa_data));

    }
}
