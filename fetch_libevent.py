#! /usr/bin/env python

"""download and extract the libevent source archive
"""

url = 'http://github.com/downloads/libevent/libevent/libevent-1.4.14b-stable.tar.gz'
hash = 'a00e037e4d3f9e4fe9893e8a2d27918c'

import sys
import os
import urllib
import tarfile
import StringIO
import tempfile
import shutil
import copy

try:
    from hashlib import md5
except ImportError:
    from md5 import md5


# python 2.4's tarfile doesn't have extractall.
def extractall(self, path="."):
    for tarinfo in self:
        if tarinfo.isdir():
            # Extract directories with a safe mode.
            tarinfo = copy.copy(tarinfo)
            tarinfo.mode = 0700
        self.extract(tarinfo, path)


def download_and_extract(url, digest):
    assert url.endswith(".tar.gz"), "can only download .tar.gz files"
    dst = os.path.abspath("libevent-src")

    if os.path.exists(dst):
        sys.exit("Error: path %s already exists" % dst)

    tmpdir = tempfile.mkdtemp(prefix="tmp-libevent-src", dir=".")
    try:
        dirname = os.path.join(tmpdir, url.split("/")[-1][:-len(".tar.gz")])
        print "downloading libevent source from %s" % url
        tgz = urllib.urlopen(url).read()
        tgz_digest = md5(tgz).hexdigest()
        if tgz_digest != digest:
            sys.exit("Error: wrong md5 sum: %r != %r" % (tgz_digest, digest))

        print "extracting to %s" % dst
        tf = tarfile.open("libevent-src.tar.gz",
                          fileobj=StringIO.StringIO(tgz),
                          mode='r:gz')
        extractall(tf, tmpdir)
        os.rename(dirname, dst)
        print "setup.py will now build libevent and link with it statically"
    finally:
        shutil.rmtree(tmpdir)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    download_and_extract(url, hash)


if __name__ == '__main__':
    main()
