
try:
    from errno import EBADF
except ImportError:
    EBADF = 9


cancel_wait_ex = IOError(EBADF, 'File descriptor was closed in another greenlet')
FileObjectClosed = IOError(EBADF, 'Bad file descriptor (FileObject was closed)')
