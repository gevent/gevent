# Make sure that libev child watchers, implicitly installed through the use
# of subprocess, do not cause waitpid() to fail to poll for processes.
# NOTE: This was only reproducible under python 2.
import gevent
from gevent import monkey
monkey.patch_all()

from multiprocessing import Process
from gevent.subprocess import Popen, PIPE


def test_invoke():
    # Run a subprocess through Popen to make sure
    # libev is handling SIGCHLD. This could *probably* be simplified to use
    # just hub.loop.install_sigchld

    p = Popen("true", stdout=PIPE, stderr=PIPE)
    gevent.sleep(0)
    p.communicate()
    gevent.sleep(0)


def f(sleep_sec):
    gevent.sleep(sleep_sec)


def test_process():
    # Launch
    p = Process(target=f, args=(1.0,))
    p.start()

    with gevent.Timeout(3):
        # Poll for up to 10 seconds. If the bug exists,
        # this will timeout because our subprocess should
        # be long gone by now
        p.join(10)


if __name__ == '__main__':
    # do a subprocess open
    test_invoke()

    test_process()
