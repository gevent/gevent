# a deadlock is possible if we import a module that runs Gevent's getaddrinfo
# with a unicode hostname, which starts Python's getaddrinfo on a thread, which
# attempts to import encodings.idna but blocks on the import lock. verify
# that Gevent avoids this deadlock.

import getaddrinfo_module
del getaddrinfo_module  # fix pyflakes
