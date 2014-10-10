"""This is the extract from test_signal.py that runs forever until it fails.

It reproduces the bug where SIGCHLD either not delivered or somehow lost and thus
if libev does not poll waitpid() periodically, popen.wait() blocks forever.

The patch that fixes it: https://bitbucket.org/denis/gevent/changeset/adb8b5ac698c
Comment out the lines in ev.c that start the timer if you want to see for yourself.

Reproduced on my machine (Linux 3.0.0-16-generic) with backend epoll and select.

With signalfd enabled (GEVENT_BACKEND=signalfd) it seems to work.
"""
from __future__ import print_function
import gevent
from contextlib import closing
import gc
import pickle
from gevent import select
from gevent import subprocess
import traceback
import sys
import os

gc.disable()

MAX_DURATION = 10


def run_test():
    child = subprocess.Popen(['/bin/true'])
    child.wait()  # << this is where it blocks


def test_main():
    # This function spawns a child process to insulate the main
    # test-running process from all the signals. It then
    # communicates with that child process over a pipe and
    # re-raises information about any exceptions the child
    # throws. The real work happens in self.run_test().
    os_done_r, os_done_w = os.pipe()
    with closing(os.fdopen(os_done_r)) as done_r:
        with closing(os.fdopen(os_done_w, 'w')) as done_w:
            child = gevent.fork()
            if not child:
                # In the child process; run the test and report results
                # through the pipe.
                try:
                    done_r.close()
                    # Have to close done_w again here because
                    # exit_subprocess() will skip the enclosing with block.
                    with closing(done_w):
                        try:
                            run_test()
                        except:
                            pickle.dump(traceback.format_exc(), done_w)
                        else:
                            pickle.dump(None, done_w)
                except:
                    print('Uh oh, raised from pickle.')
                    traceback.print_exc()
                finally:
                    os._exit(0)

            done_w.close()
            # Block for up to MAX_DURATION seconds for the test to finish.
            r, w, x = select.select([done_r], [], [], MAX_DURATION)
            if done_r in r:
                tb = pickle.load(done_r)
                assert not tb, tb
            else:
                os.kill(child, 9)
                assert False, 'Test deadlocked after %d seconds.' % MAX_DURATION


if __name__ == "__main__":
    print(gevent.get_hub())
    while True:
        test_main()
        sys.stderr.write('.')
