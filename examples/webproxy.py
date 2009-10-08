#!/usr/bin/python
from gevent import monkey; monkey.patch_all()
from gevent import wsgi
import sys
import re
import traceback
import urllib2
from urlparse import urlparse
from cgi import escape
from urllib import unquote


def application(env, start_response):
    proxy_url = 'http://127.0.0.1:%(SERVER_PORT)s/' % env
    method = env['REQUEST_METHOD']
    path = env['PATH_INFO']
    if env['QUERY_STRING']:
        path += '?' + env['QUERY_STRING']
    path = path.lstrip('/')
    if (method, path) == ('GET', ''):
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [FORM]
    elif method == 'GET':
        if '://' not in path:
            path = 'http://' + path
        try:
            try:
                r = urllib2.urlopen(path)
            except urllib2.HTTPError, ex:
                r = ex
            print '%s: %s %s' % (path, r.code, r.msg)
            headers = [(k, v) for (k, v) in r.headers.items() if k not in drop_headers]
            parsed_path = urlparse(path)
            host = (parsed_path.scheme or 'http') + '://' + parsed_path.netloc
        except Exception, ex:
            sys.stderr.write('error while reading %s:\n' % path)
            traceback.print_exc()
            tb = traceback.format_exc()
            start_response('502 Bad Gateway', [('Content-Type', 'text/html')])
            return ['<h1>%s</h1><h2>%s</h2><pre>%s</pre>' % (escape(str(ex) or ex.__class__.__name__ or 'Error'), escape(path), escape(tb))]
        #for key, value in r.headers:
        else:
            start_response('%s %s' % (r.code, r.msg), headers)
            data = r.read()
            data = fix_links(data, proxy_url, host)
            return [data]
    elif (method, path) == ('POST', ''):
        key, value = env['wsgi.input'].read().strip().split('=')
        assert key == 'url', repr(key)
        start_response('302 Found', [('Location', join(proxy_url, unquote(value)))])
    elif method == 'POST':
        start_response('404 Not Found', [])
    else:
        start_response('501 Not Implemented', [])
    return []



def join(url1, *rest):
    if not rest:
        return url1
    url2, rest = rest[0], rest[1:]
    if url1.endswith('/'):
        if url2.startswith('/'):
            return join(url1 + url2[1:], *rest)
        else:
            return join(url1 + url2, *rest)
    elif url2.startswith('/'):
        return join(url1 + url2, *rest)
    else:
        return join(url1 + '/' + url2, *rest)


def fix_links(data, proxy_url, host_url):
    """
    >>> fix_links("><img src=images/hp0.gif width=158", 'http://127.0.0.1:8088', 'www.google.com')
    '><img src="http://127.0.0.1:8088/www.google.com/images/hp0.gif" width=158'
    """
    def fix_link_cb(m):
        url = m.group('url')
        if '://' in url:
            result = m.group('before') + '"' + join(proxy_url, url) + '"'
        else:
            result = m.group('before') + '"' + join(proxy_url, host_url, url) + '"'
        #print 'replaced %r -> %r' % (m.group(0), result)
        return result
    data = _link_re_1.sub(fix_link_cb, data)
    data = _link_re_2.sub(fix_link_cb, data)
    return data

_link_re_1 = re.compile('''(?P<before>(href|src|action)\s*=\s*)(?P<quote>['"])(?P<url>[^#].*?)(?P=quote)''')
_link_re_2 = re.compile('''(?P<before>(href|src|action)\s*=\s*)(?P<url>[^'"#>][^ >]*)''')

drop_headers = ['transfer-encoding', 'set-cookie']

FORM = """<html><head>
<title>Web Proxy - gevent example</title></head><body>
<table width=60% height=100% align=center>
<tr height=30%><td align=center valign=bottom>Type in URL you want to visit and press Enter</td></tr>
<tr><td align=center valign=top>
<form action=/ method=post>
<input size=80 name=url value="http://www.google.com"/>
</form>
</td></tr>
</table></body></table>
"""

if __name__ == '__main__':
    #import doctest
    #doctest.testmod()
    print 'Serving on 8088...'
    wsgi.WSGIServer(('', 8088), application).serve_forever()

