from python cimport *
# Work around lack of absolute_import in Cython.
os = __import__('os', level=0)

# We implement __del__s in Cython so that they are safe against signals

def SocketAdapter__del__(self, close=os.close):
    fileno = self._fileno
    if fileno is not None:
        self._fileno = None
        if self._close:
            close(fileno)


def noop(self):
    pass
