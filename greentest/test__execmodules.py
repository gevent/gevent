import sys
import traceback
from greentest import walk_modules


for path, module in walk_modules():
    sys.stderr.write('%s %s\n' % (module, path))
    try:
        execfile(path)
    except Exception:
        traceback.print_exc()
