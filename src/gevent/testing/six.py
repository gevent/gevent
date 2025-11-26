import builtins

PY3 = True

exec_ = getattr(builtins, "exec")

def reraise(tp, value, tb=None): # pylint: disable=unused-argument
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value

xrange = range
string_types = (str,)
text_type = str
