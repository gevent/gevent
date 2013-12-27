"""An example how to use sendfile[1] with gevent.

[1] http://pypi.python.org/pypi/py-sendfile/
"""
from errno import EAGAIN
from sendfile import sendfile as original_sendfile
from gevent.socket import wait_write


def gevent_sendfile(out_fd, in_fd, offset, count):
    total_sent = 0
    while total_sent < count:
        try:
            _offset, sent = original_sendfile(out_fd, in_fd, offset + total_sent, count - total_sent)
            #print('%s: sent %s [%d%%]' % (out_fd, sent, 100*total_sent/count))
            total_sent += sent
        except OSError as ex:
            if ex.args[0] == EAGAIN:
                wait_write(out_fd)
            else:
                raise
    return offset + total_sent, total_sent


def patch_sendfile():
    import sendfile
    sendfile.sendfile = gevent_sendfile
