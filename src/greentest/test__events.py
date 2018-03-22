# -*- coding: utf-8 -*-
# Copyright 2018 gevent. See LICENSE.
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


import unittest

from gevent import events
from zope.interface import verify

class TestImplements(unittest.TestCase):

    def test_event_loop_blocked(self):
        verify.verifyClass(events.IEventLoopBlocked, events.EventLoopBlocked)

class TestEvents(unittest.TestCase):

    def test_is_zope(self):
        from zope import event
        self.assertIs(events.subscribers, event.subscribers)
        self.assertIs(events.notify, event.notify)

if __name__ == '__main__':
    unittest.main()
