# Copyright 2018 gevent contributors. See LICENSE for details.

import os
import unittest

from gevent import _config

class TestResolver(unittest.TestCase):

    old_resolver = None

    def setUp(self):
        if 'GEVENT_RESOLVER' in os.environ:
            self.old_resolver = os.environ['GEVENT_RESOLVER']
            del os.environ['GEVENT_RESOLVER']

    def tearDown(self):
        if self.old_resolver:
            os.environ['GEVENT_RESOLVER'] = self.old_resolver

    def test_key(self):
        self.assertEqual(_config.Resolver.environment_key, 'GEVENT_RESOLVER')

    def test_default(self):
        from gevent.resolver.thread import Resolver

        conf = _config.Resolver()
        self.assertEqual(conf.get(), Resolver)

    def test_env(self):
        from gevent.resolver.blocking import Resolver

        os.environ['GEVENT_RESOLVER'] = 'foo,bar,block,dnspython'

        conf = _config.Resolver()
        self.assertEqual(conf.get(), Resolver)

        os.environ['GEVENT_RESOLVER'] = 'dnspython'

        # The existing value is unchanged
        self.assertEqual(conf.get(), Resolver)

        # A new object reflects it
        conf = _config.Resolver()
        from gevent.resolver.dnspython import Resolver as DResolver
        self.assertEqual(conf.get(), DResolver)

    def test_set_str_long(self):
        from gevent.resolver.blocking import Resolver
        conf = _config.Resolver()
        conf.set('gevent.resolver.blocking.Resolver')

        self.assertEqual(conf.get(), Resolver)

    def test_set_str_short(self):
        from gevent.resolver.blocking import Resolver
        conf = _config.Resolver()
        conf.set('block')

        self.assertEqual(conf.get(), Resolver)

    def test_set_class(self):
        from gevent.resolver.blocking import Resolver
        conf = _config.Resolver()
        conf.set(Resolver)

        self.assertEqual(conf.get(), Resolver)


    def test_set_through_config(self):
        from gevent.resolver.thread import Resolver as Default
        from gevent.resolver.blocking import Resolver

        conf = _config.Config()
        self.assertEqual(conf.resolver, Default)

        conf.resolver = 'block'
        self.assertEqual(conf.resolver, Resolver)

if __name__ == '__main__':
    unittest.main()
