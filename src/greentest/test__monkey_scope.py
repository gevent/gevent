import sys


if 'gevent' not in sys.modules:
    from subprocess import Popen
    args = [sys.executable, '-m', 'gevent.monkey', __file__]
    p = Popen(args)
    code = p.wait()
    assert code == 0, code

else:
    from textwrap import dedent

    def use_import():
        dedent("    text")

    use_import()
