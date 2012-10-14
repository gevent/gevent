#!/usr/bin/python
# Copyright (C) 2012 Denis Bilenko (http://denisbilenko.com)
"""
Create a source distribution of gevent.

Does the following:

    - Clones the repo into a temporary location.
    - Run set_version.py that will update gevent/__init__.py.
    - Run 'python setup.py sdist'.

If --fast is provided, then fast copying with hard-links is used instead of cloning.
If --revert is provided, then copying is done and then changes are reverted.
"""
import sys
import os
import glob
import optparse
from os.path import exists, join, abspath, basename
from pipes import quote


TMPDIR = '/tmp/gevent-make-dist'
useful_files = ['gevent/core.pyx',
                'gevent/gevent.core.h',
                'gevent/gevent.core.c',
                'gevent/gevent.ares.h',
                'gevent/gevent.ares.c',
                'gevent/gevent._semaphore.c',
                'gevent/gevent._semaphore.h',
                'gevent/gevent._util.c']


def system(cmd, noisy=True):
    if noisy:
        print cmd
    res = os.system(cmd)
    if res:
        sys.exit('%r failed with %s' % (cmd, res))


def iter_status(command):
    for line in os.popen(command).readlines():
        line = line.strip()
        if line:
            assert line[1] == ' ' and line[0] != ' ' and line[2] != ' ', repr(line)
            yield line[:1], line[1:].strip()


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


def mkdir(path):
    try:
        os.mkdir(path)
    except OSError, ex:
        if ex.errno == 17:  # File exists
            return False
        raise
    return True


if __name__ == '__main__':
    main()
