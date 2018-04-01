from multiprocessing.util import spawnv_passfds as _spawnv_passfd

from gevent.hub import _get_hub_noargs as get_hub

__implements__ = ["spawnv_passfds"]
__target__ = "multiprocessing.util"


def spawnv_passfds(path, args, passfds):
    return get_hub().threadpool.apply(_spawnv_passfd, (path, args, passfds))
