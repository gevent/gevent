__all__ = ['reraise']

def reraise(tp, value, tb=None):
    raise type, value, tb     # please ignore syntax error here for Python3