import sys


def test_no_args():
    print(test_no_args.__name__)
    sys.exit(10)


def test_queues(r_q, w_q):
    print(r_q.get(timeout=5))
    w_q.put(test_queues.__name__, timeout=5)
    sys.exit(10)
