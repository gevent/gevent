import greentest
from copy import copy
# Comment the line below to see that the standard thread.local is working correct
from gevent import monkey; monkey.patch_all()


from threading import local


class A(local):
    __slots__ = ['initialized', 'obj']

    path = ''

    def __init__(self, obj):
        if not hasattr(self, 'initialized'):
            self.obj = obj
        self.path = ''


class Obj(object):
    pass

# These next two classes have to be global to avoid the leakchecks
deleted_sentinels = []
created_sentinels = []


class Sentinel(object):
    def __del__(self):
        deleted_sentinels.append(id(self))


class MyLocal(local):
    def __init__(self):
        local.__init__(self)
        self.sentinel = Sentinel()
        created_sentinels.append(id(self.sentinel))


class GeventLocalTestCase(greentest.TestCase):

    def test_copy(self):
        a = A(Obj())
        a.path = '123'
        a.obj.echo = 'test'
        b = copy(a)
        """
        Copy makes a shallow copy. Meaning that the attribute path
        has to be independent in the original and the copied object because the
        value is a string, but the attribute obj should be just reference to
        the instance of the class Obj
        """
        self.assertEqual(a.path, b.path, 'The values in the two objects must be equal')
        self.assertEqual(a.obj, b.obj, 'The values must be equal')

        b.path = '321'
        self.assertNotEqual(a.path, b.path, 'The values in the two objects must be different')

        a.obj.echo = "works"
        self.assertEqual(a.obj, b.obj, 'The values must be equal')

    def test_objects(self):
        """
        Test which failed in the eventlet?!
        """
        a = A({})
        a.path = '123'
        b = A({'one': 2})
        b.path = '123'
        self.assertEqual(a.path, b.path, 'The values in the two objects must be equal')

        b.path = '321'

        self.assertNotEqual(a.path, b.path, 'The values in the two objects must be different')

    def test_locals_collected_when_greenlet_dead_but_still_referenced(self):
        # https://github.com/gevent/gevent/issues/387
        import gevent

        my_local = MyLocal()
        my_local.sentinel = None
        if greentest.PYPY:
            import gc
            gc.collect()
        del created_sentinels[:]
        del deleted_sentinels[:]

        def demonstrate_my_local():
            # Get the important parts
            getattr(my_local, 'sentinel')

        # Create and reference greenlets
        greenlets = [gevent.spawn(demonstrate_my_local) for _ in range(5)]
        gevent.sleep()

        self.assertEqual(len(created_sentinels), len(greenlets))

        for g in greenlets:
            assert g.dead
        gevent.sleep() # let the callbacks run
        if greentest.PYPY:
            gc.collect()

        # The sentinels should be gone too
        self.assertEqual(len(deleted_sentinels), len(greenlets))

if __name__ == '__main__':
    greentest.main()
