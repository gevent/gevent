import sys
from multiprocessing.forkserver import ForkServer as _ForkServer

from gevent.os import make_nonblocking, nb_read, nb_write

__implements__ = ["ForkServer", "_forkserver", "ensure_running",
                  "get_inherited_fds", "connect_to_new_process",
                  "set_forkserver_preload"]
__target__ = "multiprocessing.forkserver"


class ForkServer(_ForkServer):
    def connect_to_new_process(self, fds):
        parent_r, parent_w = super().connect_to_new_process(fds)
        make_nonblocking(parent_r)
        make_nonblocking(parent_w)
        return parent_r, parent_w

    def ensure_running(self):
        super().ensure_running()
        make_nonblocking(self._forkserver_alive_fd)


if sys.version_info[:2] > (3, 6):
    __implements__ += ["read_signed", "write_signed"]

    from multiprocessing.forkserver import SIGNED_STRUCT


    def read_signed(fd):
        data = b''
        length = SIGNED_STRUCT.size
        while len(data) < length:
            s = nb_read(fd, length - len(data))
            if not s:
                raise EOFError('unexpected EOF')
            data += s
        return SIGNED_STRUCT.unpack(data)[0]


    def write_signed(fd, n):
        msg = SIGNED_STRUCT.pack(n)
        while msg:
            nbytes = nb_write(fd, msg)
            if nbytes == 0:
                raise RuntimeError('should not get here')
            msg = msg[nbytes:]
else:
    __implements__ += ["read_unsigned", "write_unsigned"]

    from multiprocessing.forkserver import UNSIGNED_STRUCT


    def read_unsigned(fd):
        data = b''
        length = UNSIGNED_STRUCT.size
        while len(data) < length:
            s = nb_read(fd, length - len(data))
            if not s:
                raise EOFError('unexpected EOF')
            data += s
        return UNSIGNED_STRUCT.unpack(data)[0]


    def write_unsigned(fd, n):
        msg = UNSIGNED_STRUCT.pack(n)
        while msg:
            nbytes = nb_write(fd, msg)
            if nbytes == 0:
                raise RuntimeError('should not get here')
            msg = msg[nbytes:]

_forkserver = ForkServer()
ensure_running = _forkserver.ensure_running
get_inherited_fds = _forkserver.get_inherited_fds
connect_to_new_process = _forkserver.connect_to_new_process
set_forkserver_preload = _forkserver.set_forkserver_preload
