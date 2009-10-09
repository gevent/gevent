#!/usr/bin/python
import os, re

index_name = '_build/html/index.html'
contentstable_name = '_build/html/contentstable.html'

if os.path.exists(contentstable_name):
    # replace 'insert-contenstable.html' with contestable.html
    index = open(index_name).read()
    contentstable = open(contentstable_name).read()
    index = index.replace('INSERT-contentstable.html', contentstable)
    open(index_name, 'w').write(index)
    os.unlink(contentstable_name)

    # protect email
    email_re = re.compile('<a .*?mailto.*?</a>')

    def repl(m):
        source = m.group(0)
        result = "<script type=\"text/javascript\">document.write('"
        while source:
            piece, source = source[:5], source[5:]
            result += piece + "'+'"
        return result + "')</script><noscript><small>enable javascript to see the email</small></noscript>"

    newindex, n = email_re.subn(repl, index)
    if not n:
        print 'no email found'
    else:
        assert n == 1, (n, newindex)
        open(index_name, 'w').write(newindex)

