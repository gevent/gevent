import gevent
#import socket # on windows

# iwait should not raise `LoopExit: This operation would block forever`
# or `AssertionError: Invalid switch into ...`
# if the caller of iwait causes greenlets to switch in between
# return values


def worker(i):
    # Have one of them raise an exception to test that case
    if i == 2:
        raise ValueError(i)
    return i


def main():
    finished = 0
    # Wait on a group that includes one that will already be
    # done, plus some that will finish as we watch
    done_worker = gevent.spawn(worker, "done")
    gevent.joinall((done_worker,))

    workers = [gevent.spawn(worker, i) for i in range(3)]
    workers.append(done_worker)
    for g in gevent.iwait(workers):
        finished += 1
        # Simulate doing something that causes greenlets to switch;
        # a non-zero timeout is crucial
        gevent.sleep(0.01)

    assert finished == 4

if __name__ == '__main__':
    main()
