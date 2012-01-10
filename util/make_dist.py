#!/usr/bin/python
import sys
import os
import optparse


TMPDIR = 'gevent-make-dist'


def system(cmd):
    print cmd
    res = os.system(cmd)
    if res:
        sys.exit('%r failed with %s' % (cmd, res))


def main():
    basedir = os.path.abspath(os.getcwd())
    assert os.path.exists('gevent/__init__.py'), 'Where am I?'

    parser = optparse.OptionParser()
    parser.add_option('--rsync', action='store_true')
    parser.add_option('--version')
    options, args = parser.parse_args()
    if args:
        sys.exit('Unexpected arguments: %r' % (args, ))

    os.chdir('/tmp')
    system('rm -fr ' + TMPDIR)
    os.mkdir(TMPDIR)
    os.chdir(TMPDIR)

    if options.rsync:
        options.copy_command = 'rsync -r %s .' % basedir
    else:
        options.copy_command = 'hg clone %s' % basedir

    if options.version:
        options.set_version_command = 'util/set_version.py --version %s gevent/__init__.py' % options.version
    else:
        options.set_version_command = 'util/set_version.py gevent/__init__.py'

    system(options.copy_command)
    directory = os.listdir('.')
    assert len(directory) == 1, directory
    os.chdir(directory[0])

    system(options.set_version_command)
    system('hg diff')
    system('python setup.py sdist')

    website_dir = os.path.join(os.path.dirname(basedir), 'gevent-website')
    if os.path.exists(website_dir):
        system('cp dist/gevent-*.tar.gz %s/dist' % website_dir)


if __name__ == '__main__':
    main()
