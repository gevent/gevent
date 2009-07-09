import os
import traceback

base = '../gevent'
modules = set()

for path, dirs, files in os.walk(base):
    package = 'gevent' + path.replace(base, '').replace('/', '.')
    modules.add((package, os.path.join(path, '__init__.py')))
    for f in files:
        module = None
        if f.endswith('.py'):
            module = f[:-3]
        if module:
            modules.add((package + '.' + module, os.path.join(path, f)))

for m, path in modules:
    print m, path
    try:
        execfile(path)
    except Exception:
        traceback.print_exc()
