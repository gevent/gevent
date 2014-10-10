#!/usr/bin/python
# Copyright (C) 2012 Denis Bilenko (http://denisbilenko.com)
"""
Create a source distribution of gevent.

Does the following:

    - Clones the repo into a temporary location.
    - Run set_version.py that will update gevent/__init__.py.
    - Run 'python setup.py sdist'.
"""
from __future__ import print_function
import sys
import os
import glob
import optparse
from os.path import exists, join, abspath, basename
from pipes import quote


TMPDIR = '/tmp/gevent-make-dist'


def system(cmd, noisy=True):
    if noisy:
        print(cmd)
    res = os.system(cmd)
    if res:
        sys.exit('%r failed with %s' % (cmd, res))


def makedist(*args, **kwargs):
    cwd = os.getcwd()
    try:
        return _makedist(*args, **kwargs)
    finally:
        os.chdir(cwd)


def _makedist(version=None, dest=None):
    assert exists('gevent/__init__.py'), 'Where am I?'
    basedir = abspath(os.getcwd())
    version = version or 'dev'
    set_version_command = 'util/set_version.py --version %s ./gevent/__init__.py' % version
    os.chdir('/tmp')
    system('rm -fr ' + TMPDIR)
    os.mkdir(TMPDIR)
    os.chdir(TMPDIR)

    system('git clone %s gevent' % basedir)

    directory = os.listdir('.')
    assert len(directory) == 1, directory

    os.chdir(directory[0])
    system('git branch')
    system(set_version_command)
    system('git diff', noisy=False)
    system('python setup.py -q sdist')

    dist_filename = glob.glob('dist/gevent-*.tar.gz')
    assert len(dist_filename) == 1, dist_filename
    dist_path = abspath(dist_filename[0])
    dist_filename = basename(dist_path)

    if dest:
        if os.path.isdir(dest):
            dest = join(dest, dist_filename)
    else:
        if not exists(join(basedir, 'dist')):
            os.mkdir(join(basedir, 'dist'))
        dest = join(basedir, 'dist', dist_filename)

    copy(dist_path, dest)
    return dist_path


def main():
    parser = optparse.OptionParser()
    parser.add_option('--dest')
    parser.add_option('--version')
    options, args = parser.parse_args()
    assert not args, 'Expected no arguments'
    return makedist(options.version, dest=options.dest)


def copy(source, dest):
    system('cp -a %s %s' % (quote(source), quote(dest)))


if __name__ == '__main__':
    main()
