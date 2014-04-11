import gevent
from gevent.pool import Group
from gevent.queue import Queue
from greentest import TestCase, main


class TestIMapQueue(TestCase):

    def test_imap_queue(self):
        fetches = Queue()
        validations = Queue()
        results = Queue()

        def searcher():
            fetches.put(True)
            validations.get()
            print "SEARCH DONE"
            fetches.put(StopIteration)

        def validator():
            for result in Group().imap(lambda _: _, fetches):
                print "VALIDATION PUT"
                validations.put(True)
            print "VALIDATION DONE"
            validations.put(StopIteration)
            results.put(StopIteration)
            return

        gevent.spawn(searcher)
        gevent.spawn(validator)

        results.get()

if __name__ == '__main__':
    main()
