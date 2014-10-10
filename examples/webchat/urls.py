from django.conf.urls.defaults import *
from webchat import settings

urlpatterns = patterns('webchat.chat.views',
                       ('^$', 'main'),
                       ('^a/message/new$', 'message_new'),
                       ('^a/message/updates$', 'message_updates'))

urlpatterns += patterns('django.views.static',
                        (r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'), 'serve',
                         {'document_root': settings.MEDIA_ROOT,
                          'show_indexes': True}))
