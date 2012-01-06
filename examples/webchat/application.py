#!/usr/bin/python
from gevent import monkey; monkey.patch_all()
import os
import traceback
from django.core.handlers.wsgi import WSGIHandler
from django.core.signals import got_request_exception
from django.core.management import call_command

os.environ['DJANGO_SETTINGS_MODULE'] = 'webchat.settings'


def exception_printer(sender, **kwargs):
    traceback.print_exc()


got_request_exception.connect(exception_printer)

call_command('syncdb')

application = WSGIHandler()
