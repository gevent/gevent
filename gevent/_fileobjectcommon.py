import sys
from gevent._socketcommon import EBADF


cancel_wait_ex = IOError(EBADF, 'File descriptor was closed in another greenlet')
FileObjectClosed = IOError(EBADF, 'Bad file descriptor (FileObject was closed)')

PYPY = hasattr(sys, 'pypy_version_info')
