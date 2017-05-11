# this produces syntax error on Python3

__all__ = ['reraise']


def reraise(type, value, tb):
    raise type, value, tb
