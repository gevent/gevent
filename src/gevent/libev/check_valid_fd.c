#ifndef G_CHECK_VALID_FD
#define G_CHECK_VALID_FD


#ifndef _WIN32
#include <fcntl.h>
#endif

/**
   Raises an exception if *fd* is not a valid open file handle.
   *fd* is the platform specific version; we will call vfd_open if
   needed.

   Ignore the return value for Cython; for CFFI, when GEVENT_CFFI is defined,
   returns -1 on error.
*/
int gevent_check_fd_valid(int fd)
{
// See also gevent.os._check_fd_valid

// TODO: libuv uses syscalls like poll(), epoll(), and kqueue.
// the poll one we could do because it doesn't require an
// extra file descriptor like the rest do, and which is buried in the
// loop. Why is stat not sufficient? I *think* libuv wants to detect
// non-selectable types and error out on those. But all we're
// concerned about right now is whether the file descriptor is valid
// or not.
//
// fstat() would seem to be a way to do that, but libev implements the
// same function using this method:
    int was_valid;
#ifdef _WIN32
    was_valid = vfd_open_(fd, 1); // raise python exception
    if (was_valid != -1) {
        vfd_free(fd);
    }
#else
    was_valid = fcntl(fd, F_GETFD);
    if (was_valid == -1) {
#ifndef GEVENT_CFFI
        // recall you can't use the Python API from CFFI,
        // because these functions don't hold the GIL
        PyErr_SetFromErrno(PyExc_OSError);
#endif
    }
#endif
    return was_valid;
}


#endif
