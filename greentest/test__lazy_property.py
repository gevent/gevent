from gevent.util import lazy_property

calc = []

class A(object):

    @lazy_property
    def prop(self):
        calc.append(1)
        return 1

a = A()
assert a.prop == 1
assert calc == [1], calc
assert a.prop == 1
assert calc == [1], calc
a.__dict__['prop'] = 5
assert a.prop == 5
assert calc == [1], calc
