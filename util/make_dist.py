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


TMPDIR = '/tmp/gevent-make-dist'
useful_files = ['gevent/core.pyx',
                'gevent/gevent.core.h',
                'gevent/gevent.core.c',
                'gevent/gevent.ares.h',
                'gevent/gevent.ares.c',
                'gevent/gevent._semaphore.c',
                'gevent/gevent._semaphore.h']


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


def main():
    assert os.path.exists('gevent/__init__.py'), 'Where am I?'
    basedir = os.path.abspath(os.getcwd())

    parser = optparse.OptionParser()
    parser.add_option('--fast', action='store_true', help='Rather than cloning the repo, hard link the files in it')
    parser.add_option('--revert', action='store_true', help='Same as --fast, but also do "hg revert -a" before start')
    options, args = parser.parse_args()

    if options.revert:
        options.fast = True

    if len(args) != 1:
        sys.exit('Expected one argument: version (could be "dev").')
    version = args[0]

    if version.lower() == 'dev':
        set_version_command = 'util/set_version.py gevent/__init__.py'
    else:
        set_version_command = 'util/set_version.py --version %s gevent/__init__.py' % version

    os.chdir('/tmp')
    system('rm -fr ' + TMPDIR)
    os.mkdir(TMPDIR)
    os.chdir(TMPDIR)

    if options.fast:
        system('cp -al %s .' % basedir)
    else:
        system('hg clone %s gevent' % basedir)

    directory = os.listdir('.')
    assert len(directory) == 1, directory
    os.chdir(directory[0])

    if options.fast:
        system('rm -fr build doc/_build dist')

        status_command = 'hg status --unknown --ignored'
        if options.revert:
            status_command += ' --modified --added'

        for status, name in iter_status(status_command):
            if name not in useful_files:
                os.unlink(name)

        if options.revert:
            system('hg revert -a')

        for root, dirs, files in os.walk('.', topdown=False):
            if not dirs and not files:
                print 'Removing empty directory %r' % root
                os.rmdir(root)

    system(set_version_command)
    system('hg diff', noisy=False)
    system('python setup.py -q sdist')

    dist_filename = glob.glob('dist/gevent-*.tar.gz')
    assert len(dist_filename) == 1, dist_filename
    dist_filename = os.path.abspath(dist_filename[0])

    website_dist_dir = os.path.join(os.path.dirname(basedir), 'gevent-website', 'dist')
    if os.path.exists(website_dist_dir):
        system('cp %s %s' % (dist_filename, website_dist_dir))
    system('ln -f %s %s/' % (dist_filename, TMPDIR))


if __name__ == '__main__':
    main()
