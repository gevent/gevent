import unittest
from copy import copy
# Comment the line below to see that the standard thread.local is working correct
from gevent import monkey; monkey.patch_all()


from threading import local
class A(local):
    __slots__ = ['initialized','obj']

    path = ''
    def __init__(self, obj):
        if not  hasattr(self, 'initialized'):
            self.obj = obj
        self.path = ''

class Obj(object):
    pass

class GeventLocalTestCase(unittest.TestCase):

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
        b = A({'one':2})
        b.path = '123'
        self.assertEqual(a.path, b.path, 'The values in the two objects must be equal')

        b.path = '321'

        self.assertNotEqual(a.path, b.path, 'The values in the two objects must be different')

if __name__ == '__main__':
    unittest.main()
