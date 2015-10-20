try:
    from gevent._fileobjectposix import FileObjectPosix
    __all__ = ['FileObjectPosix', ]
except ImportError:
    import sys
    assert sys.platform.startswith('win'), "Should be able to import except on Windows"
    __all__ = []
