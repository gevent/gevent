
import gevent
from gevent.supervisor import Supervisor

def fel(x):
    i = 0
    while True:
        gevent.sleep(0.5)
        i += 1
        print(i, x)
        if i == x:
            raise ValueError


# Test rest for one
def test_rest_for_one():
    sv = Supervisor(strategy=Strategy.REST_FOR_ONE)
    sv.supress_errors()
    sv.start_child(fel, 50)
    sv.start_child(fel, 3)
    sv.start_child(fel, 20)


# Test one for all
def test_one_for_all():
    sv = Supervisor(strategy=Strategy.ONE_FOR_ALL)
    sv.supress_errors()
    sv.start_child(fel, 5)
    sv.start_child(fel, 20)


# Test one for one
def test_one_for_one():
    sv = Supervisor()
    sv.supress_errors()
    sv.start_child(fel, 5)
    sv.start_child(fel, 20)



if __name__ == '__main__':
    test_rest_for_one()
    gevent.sleep(20)  # TODO : add join
