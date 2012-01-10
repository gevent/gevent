#!/usr/bin/python
import sys
import os
import glob
import optparse


TMPDIR = 'gevent-make-dist'


def system(cmd):
    print cmd
    res = os.system(cmd)
    if res:
        sys.exit('%r failed with %s' % (cmd, res))


def main():
    assert os.path.exists('gevent/__init__.py'), 'Where am I?'
    basedir = os.path.abspath(os.getcwd())

    parser = optparse.OptionParser()
    parser.add_option('--rsync', action='store_true')
    options, args = parser.parse_args()

    if len(args) != 1:
        sys.exit('Expected one argument: version (could be "dev")')

    version = args[0]

    if version.lower() == 'dev':
        set_version_command = 'util/set_version.py gevent/__init__.py'
    else:
        set_version_command = 'util/set_version.py --version %s gevent/__init__.py' % version

    if options.rsync:
        copy_command = 'rsync -r %s .' % basedir
    else:
        copy_command = 'hg clone %s' % basedir

    os.chdir('/tmp')
    system('rm -fr ' + TMPDIR)
    os.mkdir(TMPDIR)
    os.chdir(TMPDIR)

    system(copy_command)
    directory = os.listdir('.')
    assert len(directory) == 1, directory
    os.chdir(directory[0])

    system(set_version_command)
    system('hg diff')
    if options.rsync:
        system('rm -fr dist')
    system('python setup.py sdist')

    dist_filename = glob.glob('dist/gevent-*.tar.gz')
    assert len(dist_filename) == 1, dist_filename
    dist_filename = os.path.abspath(dist_filename[0])

    website_dir = os.path.join(os.path.dirname(basedir), 'gevent-website')
    if os.path.exists(website_dir):
        system('cp %s %s/dist' % (dist_filename, website_dir))
    system('ln -fs %s /tmp' % dist_filename)


if __name__ == '__main__':
    main()
