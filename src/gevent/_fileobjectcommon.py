
try:
    from errno import EBADF
except ImportError:
    EBADF = 9

from io import TextIOWrapper

cancel_wait_ex = IOError(EBADF, 'File descriptor was closed in another greenlet')
FileObjectClosed = IOError(EBADF, 'Bad file descriptor (FileObject was closed)')

class FileObjectBase(object):
    """
    Internal base class to ensure a level of consistency
    between FileObjectPosix and FileObjectThread
    """

    # List of methods we delegate to the wrapping IO object, if they
    # implement them and we do not.
    _delegate_methods = (
        # General methods
        'flush',
        'fileno',
        'writable',
        'readable',
        'seek',
        'seekable',
        'tell',

        # Read
        'read',
        'readline',
        'readlines',
        'read1',

        # Write
        'write',
        'writelines',
        'truncate',
    )


    # Whether we are translating universal newlines or not.
    _translate = False

    def __init__(self, io, closefd):
        """
        :param io: An io.IOBase-like object.
        """
        self._io = io
        # We don't actually use this property ourself, but we save it (and
        # pass it along) for compatibility.
        self._close = closefd

        if self._translate:
            # This automatically handles delegation.
            self.translate_newlines(None)
        else:
            self._do_delegate_methods()


    io = property(lambda s: s._io,
                  # Historically we either hand-wrote all the delegation methods
                  # to use self.io, or we simply used __getattr__ to look them up at
                  # runtime. This meant people could change the io attribute on the fly
                  # and it would mostly work (subprocess.py used to do that). We don't recommend
                  # that, but we still support it.
                  lambda s, nv: setattr(s, '_io', nv) or s._do_delegate_methods())

    def _do_delegate_methods(self):
        for meth_name in self._delegate_methods:
            meth = getattr(self._io, meth_name, None)
            implemented_by_class = hasattr(type(self), meth_name)
            if meth and not implemented_by_class:
                setattr(self, meth_name, self._wrap_method(meth))
            elif hasattr(self, meth_name) and not implemented_by_class:
                delattr(self, meth_name)

    def _wrap_method(self, method):
        """
        Wrap a method we're copying into our dictionary from the underlying
        io object to do something special or different, if necessary.
        """
        return method

    def translate_newlines(self, mode, *text_args, **text_kwargs):
        wrapper = TextIOWrapper(self._io, *text_args, **text_kwargs)
        if mode:
            wrapper.mode = mode
        self.io = wrapper
        self._translate = True

    @property
    def closed(self):
        """True if the file is closed"""
        return self._io is None

    def close(self):
        if self._io is None:
            return

        io = self._io
        self._io = None
        self._do_close(io, self._close)

    def _do_close(self, io, closefd):
        raise NotImplementedError()

    def __getattr__(self, name):
        if self._io is None:
            raise FileObjectClosed()
        return getattr(self._io, name)

    def __repr__(self):
        return '<%s _fobj=%r%s>' % (self.__class__.__name__, self.io, self._extra_repr())

    def _extra_repr(self):
        return ''
