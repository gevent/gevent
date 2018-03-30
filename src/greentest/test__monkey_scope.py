import sys


if 'gevent' not in sys.modules:
    from subprocess import Popen
    from subprocess import PIPE
    # Run a simple script
    args = [sys.executable, '-m', 'gevent.monkey', __file__]
    p = Popen(args)
    code = p.wait()
    assert code == 0, code

    # Run a __main__ inside a package.
    args = [sys.executable, '-m', 'gevent.monkey', 'monkey_package']
    p = Popen(args, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    lines = out.splitlines()
    assert lines[0].endswith(b'__main__.py'), (out, err)
    assert lines[1] == b'__main__', (lines, out, err)
    # Python 3.7 tends to produce some inscrutable
    # warning from importlib._bootstrap.py on stderr
    # "ImportWarning: can't resolve package from __spec__ or __package__".
    # So we don't check that err is empty.
else:
    from textwrap import dedent

    def use_import():
        dedent("    text")

    use_import()
