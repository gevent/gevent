#!/usr/bin/python
"""Update __version__, version_info and add __changeset__.

'dev' in version_info should be replaced with alpha|beta|candidate|final
'dev' in __version__ should be replaced with a|b|rc|<empty string>
"""

from __future__ import print_function
import sys
import os
import re
from optparse import OptionParser
from distutils.version import LooseVersion


version_re = re.compile("^__version__\s*=\s*'([^']+)'", re.M)
version_info_re = re.compile(r"^version_info\s*=\s*([^\n]+)", re.M)
strict_version_re = re.compile(r'^(\d+) \. (\d+) (\. (\d+))? ([ab](\d+))?$', re.VERBOSE)


def read(command):
    popen = os.popen(command)
    data = popen.read()
    retcode = popen.close()
    if retcode:
        sys.exit('Failed (%s) to run %r' % (retcode, command))
    return data.strip()


def get_changeset():
    return read('git describe --tags --always --dirty --long')


def get_version_info(version):
    """
    >>> get_version_info('0.13.6')
    (0, 13, 6, 'final', 0)
    >>> get_version_info('1.1')
    (1, 1, 0, 'final', 0)
    >>> get_version_info('1')
    (1, 0, 0, 'final', 0)
    >>> get_version_info('1.0dev1')
    (1, 0, 0, 'dev', 1)
    >>> get_version_info('1.0a3')
    (1, 0, 0, 'alpha', 3)
    >>> get_version_info('1.0rc1')
    (1, 0, 0, 'candidate', 1)
    """

    repl = {'a': 'alpha',
            'b': 'beta',
            'rc': 'candidate',
            'dev': 'dev'}

    components = LooseVersion(version).version
    result = []

    for component in components:
        if isinstance(component, int):
            result.append(component)
        else:
            while len(result) < 3:
                result.append(0)
            component = repl[component]
            result.append(component)

    while len(result) < 3:
        result.append(0)

    if len(result) == 3:
        result.append('final')
        result.append(0)

    return tuple(result)


def modify_version(filename, new_version):
    # return (current_contents, modified_contents, is_match)
    original_data = open(filename).read()
    assert '__changeset__' not in original_data, 'Must revert the old update first'
    data = original_data

    if new_version:
        new_version_info = get_version_info(new_version)

        def repl_version_info(m):
            return 'version_info = %s' % (new_version_info, )

        data, count = version_info_re.subn(repl_version_info, data)
        if not count:
            raise AssertionError('version_info not found in %s' % filename)
        if count != 1:
            raise AssertionError('version_info found more than once in %s' % filename)

    def repl_version(m):
        result = m.group(0).replace(m.group(1), new_version or m.group(1))
        result += "\n__changeset__ = '%s'" % get_changeset()
        return result

    data, count = version_re.subn(repl_version, data)
    if not count:
        raise AssertionError('__version__ not found in %s' % filename)
    if count != 1:
        raise AssertionError('__version__ found more than once in %s' % filename)

    return original_data, data


def unlink(path):
    try:
        os.unlink(path)
    except OSError as ex:
        if ex.errno == 2:  # No such file or directory
            return
        raise


def write(filename, data):
    # intentionally breaking links here so that util/makedist.py can use "cp --link"
    tmpname = filename + '.tmp.%s' % os.getpid()
    f = open(tmpname, 'w')
    try:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
        f.close()
        os.rename(tmpname, filename)
    except:
        unlink(tmpname)
        raise


def main():
    global options
    parser = OptionParser()
    parser.add_option('--version', default='dev')
    parser.add_option('--dry-run', action='store_true')
    options, args = parser.parse_args()
    assert len(args) == 1, 'One argument is expected, got %s' % len(args)
    version = options.version
    if version.lower() == 'dev':
        version = ''
    if version and strict_version_re.match(version) is None:
        sys.stderr.write('WARNING: Not a strict version: %r (bdist_msi will fail)' % version)
    filename = args[0]
    original_content, new_content = modify_version(filename, version)
    if options.dry_run:
        tmpname = '/tmp/' + os.path.basename(filename) + '.set_version'
        write(tmpname, new_content)
        if not os.system('diff -u %s %s' % (filename, tmpname)):
            sys.exit('No differences applied')
    else:
        write(filename, new_content)
        print('Updated %s' % filename)


if __name__ == '__main__':
    main()
