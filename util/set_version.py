#!/usr/bin/python
"""Update __version__, version_info and add __changeset__.

'dev' in version_info should be replaced with alpha|beta|candidate|final
'dev' in __version__ should be replaced with a|b|rc|<empty string>
"""

import sys
import os
import re
from optparse import OptionParser
from distutils.version import LooseVersion


version_re = re.compile("__version__\s*=\s*'([^']+)'", re.M)
version_info_re = re.compile(r"version_info\s*=\s*([^\n]+)")
changeset_re = re.compile("__changeset__\s*=\s*'([^']+)'", re.M)
hg_changeset_re = re.compile('changeset:\s+([^\s$]+)', re.M)
strict_version_re = re.compile(r'^(\d+) \. (\d+) (\. (\d+))? ([ab](\d+))?$', re.VERBOSE)


def get_changeset():
    hg_head_command = os.popen('hg head')
    data = hg_head_command.read()
    retcode = hg_head_command.close()
    if retcode:
        sys.exit('Failed (%s) to run "hg head"' % retcode)
    m = hg_changeset_re.search(data)
    if m is not None:
        return m.group(1)


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
    """

    repl = {'a': 'alpha',
            'b': 'beta',
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


def write(filename, data):
    f = open(filename, 'w')
    f.write(data)
    f.flush()
    os.fsync(f.fileno())
    f.close()


def main():
    global options
    parser = OptionParser()
    parser.add_option('--version')
    options, args = parser.parse_args()
    if options.version:
        if strict_version_re.match(options.version) is None:
            sys.exit('Not a strict version: %r (bdist_msi will fail)' % options.version)
    assert len(args) == 1, args
    filename = args[0]
    original_content, new_content = modify_version(filename, options.version)
    write(filename, new_content)
    print 'Updated %s' % filename


if __name__ == '__main__':
    main()
