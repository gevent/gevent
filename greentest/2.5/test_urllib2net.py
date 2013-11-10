#!/usr/bin/env python

import unittest
from test import test_support
from test_urllib2 import sanepathname2url

import socket
import urllib2
import sys
import os
import mimetools

class URLTimeoutTest(unittest.TestCase):

    TIMEOUT = 10.0

    def setUp(self):
        socket.setdefaulttimeout(self.TIMEOUT)

    def tearDown(self):
        socket.setdefaulttimeout(None)

    def testURLread(self):
        f = urllib2.urlopen("http://www.python.org/")
        x = f.read()


class AuthTests(unittest.TestCase):
    """Tests urllib2 authentication features."""

## Disabled at the moment since there is no page under python.org which
## could be used to HTTP authentication.
#
#    def test_basic_auth(self):
#        import httplib
#
#        test_url = "http://www.python.org/test/test_urllib2/basic_auth"
#        test_hostport = "www.python.org"
#        test_realm = 'Test Realm'
#        test_user = 'test.test_urllib2net'
#        test_password = 'blah'
#
#        # failure
#        try:
#            urllib2.urlopen(test_url)
#        except urllib2.HTTPError, exc:
#            self.assertEqual(exc.code, 401)
#        else:
#            self.fail("urlopen() should have failed with 401")
#
#        # success
#        auth_handler = urllib2.HTTPBasicAuthHandler()
#        auth_handler.add_password(test_realm, test_hostport,
#                                  test_user, test_password)
#        opener = urllib2.build_opener(auth_handler)
#        f = opener.open('http://localhost/')
#        response = urllib2.urlopen("http://www.python.org/")
#
#        # The 'userinfo' URL component is deprecated by RFC 3986 for security
#        # reasons, let's not implement it!  (it's already implemented for proxy
#        # specification strings (that is, URLs or authorities specifying a
#        # proxy), so we must keep that)
#        self.assertRaises(httplib.InvalidURL,
#                          urllib2.urlopen, "http://evil:thing@example.com")


class CloseSocketTest(unittest.TestCase):

    def test_close(self):
        import socket, httplib, gc

        # calling .close() on urllib2's response objects should close the
        # underlying socket

        # delve deep into response to fetch socket._socketobject
        response = urllib2.urlopen("http://www.python.org/")
        abused_fileobject = response.fp
        self.assert_(abused_fileobject.__class__ is socket._fileobject)
        httpresponse = abused_fileobject._sock
        self.assert_(httpresponse.__class__ is httplib.HTTPResponse)
        fileobject = httpresponse.fp
        self.assert_(fileobject.__class__ is socket._fileobject)

        self.assert_(not fileobject.closed)
        response.close()
        self.assert_(fileobject.closed)

class urlopenNetworkTests(unittest.TestCase):
    """Tests urllib2.urlopen using the network.

    These tests are not exhaustive.  Assuming that testing using files does a
    good job overall of some of the basic interface features.  There are no
    tests exercising the optional 'data' and 'proxies' arguments.  No tests
    for transparent redirection have been written.

    setUp is not used for always constructing a connection to
    http://www.python.org/ since there a few tests that don't use that address
    and making a connection is expensive enough to warrant minimizing unneeded
    connections.

    """

    def test_basic(self):
        # Simple test expected to pass.
        open_url = urllib2.urlopen("http://www.python.org/")
        for attr in ("read", "close", "info", "geturl"):
            self.assert_(hasattr(open_url, attr), "object returned from "
                            "urlopen lacks the %s attribute" % attr)
        try:
            self.assert_(open_url.read(), "calling 'read' failed")
        finally:
            open_url.close()

    def test_info(self):
        # Test 'info'.
        open_url = urllib2.urlopen("http://www.python.org/")
        try:
            info_obj = open_url.info()
        finally:
            open_url.close()
            self.assert_(isinstance(info_obj, mimetools.Message),
                         "object returned by 'info' is not an instance of "
                         "mimetools.Message")
            self.assertEqual(info_obj.getsubtype(), "html")

    def test_geturl(self):
        # Make sure same URL as opened is returned by geturl.
        URL = "http://www.python.org/"
        open_url = urllib2.urlopen(URL)
        try:
            gotten_url = open_url.geturl()
        finally:
            open_url.close()
        self.assertEqual(gotten_url, URL)

    def test_bad_address(self):
        # Make sure proper exception is raised when connecting to a bogus
        # address.
        self.assertRaises(IOError,
                          # SF patch 809915:  In Sep 2003, VeriSign started
                          # highjacking invalid .com and .net addresses to
                          # boost traffic to their own site.  This test
                          # started failing then.  One hopes the .invalid
                          # domain will be spared to serve its defined
                          # purpose.
                          # urllib2.urlopen, "http://www.sadflkjsasadf.com/")
                          urllib2.urlopen, "http://www.python.invalid./")


class OtherNetworkTests(unittest.TestCase):
    def setUp(self):
        if 0:  # for debugging
            import logging
            logger = logging.getLogger("test_urllib2net")
            logger.addHandler(logging.StreamHandler())

    def test_range (self):
        req = urllib2.Request("http://www.python.org",
                              headers={'Range': 'bytes=20-39'})
        result = urllib2.urlopen(req)
        data = result.read()
        self.assertEqual(len(data), 20)

    # XXX The rest of these tests aren't very good -- they don't check much.
    # They do sometimes catch some major disasters, though.

    def test_ftp(self):
        urls = [
            'ftp://www.python.org/pub/python/misc/sousa.au',
            'ftp://www.python.org/pub/tmp/blat',
            'ftp://gatekeeper.research.compaq.com/pub/DEC/SRC'
                '/research-reports/00README-Legal-Rules-Regs',
            ]
        self._test_urls(urls, self._extra_handlers())

    def test_gopher(self):
        import warnings
        warnings.filterwarnings("ignore",
                                "the gopherlib module is deprecated",
                                DeprecationWarning,
                                "urllib2$")
        urls = [
            # Thanks to Fred for finding these!
            'gopher://gopher.lib.ncsu.edu./11/library/stacks/Alex',
            'gopher://gopher.vt.edu.:10010/10/33',
            ]
        self._test_urls(urls, self._extra_handlers())

    def test_file(self):
        TESTFN = test_support.TESTFN
        f = open(TESTFN, 'w')
        try:
            f.write('hi there\n')
            f.close()
            urls = [
                'file:'+sanepathname2url(os.path.abspath(TESTFN)),

                # XXX bug, should raise URLError
                #('file://nonsensename/etc/passwd', None, urllib2.URLError)
                ('file://nonsensename/etc/passwd', None, (EnvironmentError, socket.error))
                ]
            self._test_urls(urls, self._extra_handlers())
        finally:
            os.remove(TESTFN)

    def test_http(self):
        urls = [
            'http://www.espn.com/', # redirect
            'http://www.python.org/Spanish/Inquistion/',
            ('http://www.python.org/cgi-bin/faqw.py',
             'query=pythonistas&querytype=simple&casefold=yes&req=search', None),
            'http://www.python.org/',
            ]
        self._test_urls(urls, self._extra_handlers())

    # XXX Following test depends on machine configurations that are internal
    # to CNRI.  Need to set up a public server with the right authentication
    # configuration for test purposes.

##     def test_cnri(self):
##         if socket.gethostname() == 'bitdiddle':
##             localhost = 'bitdiddle.cnri.reston.va.us'
##         elif socket.gethostname() == 'bitdiddle.concentric.net':
##             localhost = 'localhost'
##         else:
##             localhost = None
##         if localhost is not None:
##             urls = [
##                 'file://%s/etc/passwd' % localhost,
##                 'http://%s/simple/' % localhost,
##                 'http://%s/digest/' % localhost,
##                 'http://%s/not/found.h' % localhost,
##                 ]

##             bauth = HTTPBasicAuthHandler()
##             bauth.add_password('basic_test_realm', localhost, 'jhylton',
##                                'password')
##             dauth = HTTPDigestAuthHandler()
##             dauth.add_password('digest_test_realm', localhost, 'jhylton',
##                                'password')

##             self._test_urls(urls, self._extra_handlers()+[bauth, dauth])

    def _test_urls(self, urls, handlers):
        import socket
        import time
        import logging
        debug = logging.getLogger("test_urllib2").debug

        urllib2.install_opener(urllib2.build_opener(*handlers))

        for url in urls:
            if isinstance(url, tuple):
                url, req, expected_err = url
            else:
                req = expected_err = None
            debug(url)
            try:
                f = urllib2.urlopen(url, req)
            except (IOError, socket.error, OSError) as err:
                debug(err)
                if expected_err:
                    msg = ("Didn't get expected error(s) %s for %s %s, got %s" %
                           (expected_err, url, req, err))
                    self.assert_(isinstance(err, expected_err), msg)
            else:
                buf = f.read()
                f.close()
                debug("read %d bytes" % len(buf))
            debug("******** next url coming up...")
            time.sleep(0.1)

    def _extra_handlers(self):
        handlers = []

        handlers.append(urllib2.GopherHandler)

        cfh = urllib2.CacheFTPHandler()
        cfh.setTimeout(1)
        handlers.append(cfh)

        return handlers


def test_main():
    test_support.requires("network")
    test_support.run_unittest(URLTimeoutTest,
                              urlopenNetworkTests,
                              AuthTests,
                              OtherNetworkTests,
                              CloseSocketTest,
                              )

if __name__ == "__main__":
    test_main()
