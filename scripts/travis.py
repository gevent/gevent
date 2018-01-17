# -*- coding: utf-8 -*-
"""


"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

commands = {}

def command(func):
    commands[func.__name__] = func

@command
def fold_start():
    name = sys.argv[2]
    msg = sys.argv[3]
    sys.stdout.write('travis_fold:start:')
    sys.stdout.write(name)
    sys.stdout.write(chr(0o33))
    sys.stdout.write('[33;1m')
    sys.stdout.write(msg)
    sys.stdout.write(chr(0o33))
    sys.stdout.write('[33;0m')

@command
def fold_end():
    name = sys.argv[2]
    sys.stdout.write("\ntravis_fold:end:")
    sys.stdout.write(name)
    sys.stdout.write("\r\n")


def main():
    cmd = sys.argv[1]
    commands[cmd]()


if __name__ == '__main__':
    main()
