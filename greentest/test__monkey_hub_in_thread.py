from gevent.monkey import patch_all
patch_all(thread=False)
from threading import Thread
import time

# The first time we init the hub is in the native
# thread with time.sleep().
# See #687


def func():
    time.sleep()


def main():
    threads = []
    for _ in range(2):
        th = Thread(target=func)
        th.start()
        threads.append(th)
    for th in threads:
        th.join()


if __name__ == '__main__':
    main()
