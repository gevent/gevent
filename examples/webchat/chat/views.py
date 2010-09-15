import uuid
import simplejson
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.http import HttpResponse
from gevent.event import Event
from webchat import settings


class ChatRoom(object):
    cache_size = 200

    def __init__(self):
        self.cache = []
        self.new_message_event = Event()

    def main(self, request):
        if self.cache:
            request.session['cursor'] = self.cache[-1]['id']
        return render_to_response('index.html', {'MEDIA_URL': settings.MEDIA_URL, 'messages': self.cache})

    def message_new(self, request):
        name = request.META.get('REMOTE_ADDR') or 'Anonymous'
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for and name == '127.0.0.1':
            name = forwarded_for
        msg = create_message(name, request.POST['body'])
        self.cache.append(msg)
        if len(self.cache) > self.cache_size:
            self.cache = self.cache[-self.cache_size:]
        self.new_message_event.set()
        self.new_message_event.clear()
        return json_response(msg)

    def message_updates(self, request):
        cursor = request.session.get('cursor')
        if not self.cache or cursor == self.cache[-1]['id']:
            self.new_message_event.wait()
        assert cursor != self.cache[-1]['id'], cursor
        try:
            for index, m in enumerate(self.cache):
                if m['id'] == cursor:
                    return json_response({'messages': self.cache[index + 1:]})
            return json_response({'messages': self.cache})
        finally:
            if self.cache:
                request.session['cursor'] = self.cache[-1]['id']
            else:
                request.session.pop('cursor', None)

room = ChatRoom()
main = room.main
message_new = room.message_new
message_updates = room.message_updates


def create_message(from_, body):
    data = {'id': str(uuid.uuid4()), 'from': from_, 'body': body}
    data['html'] = render_to_string('message.html', dictionary={'message': data})
    return data


def json_response(value, **kwargs):
    kwargs.setdefault('content_type', 'text/javascript; charset=UTF-8')
    return HttpResponse(simplejson.dumps(value), **kwargs)
