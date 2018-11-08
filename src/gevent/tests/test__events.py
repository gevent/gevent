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

    def test_mem_threshold(self):
        verify.verifyClass(events.IMemoryUsageThresholdExceeded,
                           events.MemoryUsageThresholdExceeded)
        verify.verifyObject(events.IMemoryUsageThresholdExceeded,
                            events.MemoryUsageThresholdExceeded(0, 0, 0))

    def test_mem_decreased(self):
        verify.verifyClass(events.IMemoryUsageUnderThreshold,
                           events.MemoryUsageUnderThreshold)
        verify.verifyObject(events.IMemoryUsageUnderThreshold,
                            events.MemoryUsageUnderThreshold(0, 0, 0, 0))


class TestEvents(unittest.TestCase):

    def test_is_zope(self):
        from zope import event
        self.assertIs(events.subscribers, event.subscribers)
        self.assertIs(events.notify, event.notify)

if __name__ == '__main__':
    unittest.main()
