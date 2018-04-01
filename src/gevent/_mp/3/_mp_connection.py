import multiprocessing.reduction
from io import BytesIO
from multiprocessing.connection import reduce_connection, _ConnectionBase as __ConnectionBase, Connection as _Connection
from pickletools import dis, optimize

from gevent.os import make_nonblocking, nb_read, nb_write

__implements__ = ["_ConnectionBase", "Connection"]
__target__ = "multiprocessing.connection"


class _ConnectionBase(__ConnectionBase):
    def __init__(self, handle, readable=True, writable=True):
        super(_ConnectionBase, self).__init__(handle, readable, writable)
        make_nonblocking(handle)


class Connection(_ConnectionBase, _Connection):
    _write = nb_write
    _read = nb_read

    def _send(self, buf, write=_write):
        return super()._send(buf, write)

    def _recv(self, size, read=_read):
        return super()._recv(size, read)

def dump(obj, file, protocol=None):
    out = BytesIO()
    multiprocessing.reduction.ForkingPickler(out, protocol).dump(obj)
    out_bytes = bytes(out.getbuffer())
    out_bytes = optimize(out_bytes)
    dis(out_bytes)
    file.write(out_bytes)

#multiprocessing.reduction.dump = dump
multiprocessing.reduction.register(Connection, reduce_connection)
