import uuid
import simplejson
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.http import HttpResponse
from gevent.event import Event
from webchat import settings

messages = []
MESSAGES_SIZE = 200
new_message_event = Event()


def new_message(from_, body):
    data = {'id': str(uuid.uuid4()), 'from': from_, 'body': body}
    data['html'] = render_to_string('message.html', dictionary={'message': data})
    return data

def last_message_id():
    if messages:
        return messages[-1]['id']

def main(request):
    if messages:
        request.session['cursor'] = messages[-1]['id']
    return render_to_response('index.html', {'MEDIA_URL': settings.MEDIA_URL, 'messages': messages})

def message_new(request):
    name = request.META.get('REMOTE_ADDR') or 'Anonymous'
    msg = new_message(name, request.POST['body'])
    messages.append(msg)
    if len(messages) > MESSAGES_SIZE:
        del messages[0]
    new_message_event.set()
    new_message_event.clear()
    return json_response(msg)

def message_updates(request):
    cursor = request.session.get('cursor')
    if cursor == last_message_id():
        new_message_event.wait()
    assert cursor != last_message_id(), cursor
    try:
        for index, m in enumerate(messages):
            if m['id'] == cursor:
                return json_response({'messages': messages[index+1:]})
        return json_response({'messages': messages})
    finally:
        if messages:
            request.session['cursor'] = messages[-1]['id']
        else:
            request.session.pop('cursor', None)

def json_response(value, **kwargs):
    kwargs.setdefault('content_type', 'text/javascript; charset=UTF-8')
    return HttpResponse(simplejson.dumps(value), **kwargs)

