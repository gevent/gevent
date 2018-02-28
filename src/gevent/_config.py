# Copyright (c) 2018 gevent. See LICENSE for details.
"""
gevent tunables.

This should be used as ``from gevent import config``. That variable
is an object of :class:`Config`.

.. versionadded:: 1.3a2
"""

from __future__ import print_function, absolute_import, division

import importlib
import os
import sys
import textwrap

from gevent._compat import string_types

__all__ = [
    'config',
]

ALL_SETTINGS = []

class SettingType(type):
    # pylint:disable=bad-mcs-classmethod-argument

    def __new__(cls, name, bases, cls_dict):
        if name == 'Setting':
            return type.__new__(cls, name, bases, cls_dict)

        cls_dict["order"] = len(ALL_SETTINGS)
        if 'name' not in cls_dict:
            cls_dict['name'] = name.lower()

        if 'environment_key' not in cls_dict:
            cls_dict['environment_key'] = 'GEVENT_' + cls_dict['name'].upper()


        new_class = type.__new__(cls, name, bases, cls_dict)
        new_class.fmt_desc(cls_dict.get("desc", ""))
        new_class.__doc__ = new_class.desc
        ALL_SETTINGS.append(new_class)

        if new_class.document:
            setting_name = cls_dict['name']

            def getter(self):
                return self.settings[setting_name].get()

            def setter(self, value): # pragma: no cover
                # The setter should never be hit, Config has a
                # __setattr__ that would override. But for the sake
                # of consistency we provide one.
                self.settings[setting_name].set(value)

            prop = property(getter, setter, doc=new_class.__doc__)

            setattr(Config, cls_dict['name'], prop)
        return new_class

    def fmt_desc(cls, desc):
        desc = textwrap.dedent(desc).strip()
        if hasattr(cls, 'shortname_map'):
            desc += (
                "\n\nThis is an importable value. It can be "
                "given as a string naming an importable object, "
                "or a list of strings in preference order and the first "
                "successfully importable object will be used. (Separate values "
                "in the environment variable with commas.) "
                "It can also be given as the callable object itself (in code). "
            )
            if cls.shortname_map:
                desc += "Shorthand names for default objects are %r" % (list(cls.shortname_map),)
        if getattr(cls.validate, '__doc__'):
            desc += '\n\n' + textwrap.dedent(cls.validate.__doc__).strip()
        if isinstance(cls.default, str) and hasattr(cls, 'shortname_map'):
            default = "`%s`" % (cls.default,)
        else:
            default = "`%r`" % (cls.default,)
        desc += "\n\nThe default value is %s" % (default,)
        desc += ("\n\nThe environment variable ``%s`` "
                 "can be used to control this." % (cls.environment_key,))
        setattr(cls, "desc", desc)
        return desc

def validate_invalid(value):
    raise ValueError("Not a valid value: %r" % (value,))

def validate_bool(value):
    """
    This is a boolean value.

    In the environment variable, it may be given as ``1``, ``true``,
    ``on`` or ``yes`` for `True`, or ``0``, ``false``, ``off``, or
    ``no`` for `False`.
    """
    if isinstance(value, string_types):
        value = value.lower().strip()
        if value in ('1', 'true', 'on', 'yes'):
            value = True
        elif value in ('0', 'false', 'off', 'no') or not value:
            value = False
        else:
            raise ValueError("Invalid boolean string: %r" % (value,))
    return bool(value)

def validate_anything(value):
    return value

class Setting(object):
    name = None
    value = None
    validate = staticmethod(validate_invalid)
    default = None
    environment_key = None
    document = True

    desc = """\

    A long ReST description.

    The first line should be a single sentence.

    """

    def _convert(self, value):
        if isinstance(value, string_types):
            return value.split(',')
        return value

    def _default(self):
        result = os.environ.get(self.environment_key, self.default)
        result = self._convert(result)
        return result

    def get(self):
        # If we've been specifically set, return it
        if 'value' in self.__dict__:
            return self.value
        # Otherwise, read from the environment and reify
        # so we return consistent results.
        self.value = self.validate(self._default())
        return self.value

    def set(self, val):
        self.value = self.validate(self._convert(val))


Setting = SettingType('Setting', (Setting,), dict(Setting.__dict__))

def make_settings():
    """
    Return fresh instances of all classes defined in `ALL_SETTINGS`.
    """
    settings = {}
    for setting_kind in ALL_SETTINGS:
        setting = setting_kind()
        assert setting.name not in settings
        settings[setting.name] = setting
    return settings


class Config(object):
    """
    Global configuration for gevent.

    There is one instance of this object at ``gevent.config``. If you
    are going to make changes in code, instead of using the documented
    environment variables, you need to make the changes before using
    any parts of gevent that might need those settings. For example::

        >>> from gevent import config
        >>> config.fileobject = 'thread'

        >>> from gevent import fileobject
        >>> fileobject.FileObject.__name__
        'FileObjectThread'

    .. versionadded:: 1.3a2

    """

    def __init__(self):
        self.settings = make_settings()

    def __getattr__(self, name):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %r" % name)
        return self.settings[name].get()

    def __setattr__(self, name, value):
        if name != "settings" and name in self.settings:
            self.set(name, value)
        else:
            super(Config, self).__setattr__(name, value)

    def set(self, name, value):
        if name not in self.settings:
            raise AttributeError("No configuration setting for: %r" % name)
        self.settings[name].set(value)

    def __dir__(self):
        return list(self.settings)


class ImportableSetting(object):

    def _import(self, path, _NONE=object):
        # pylint:disable=too-many-branches
        if isinstance(path, list):
            if not path:
                raise ImportError('Cannot import from empty list: %r' % (path, ))

            for item in path[:-1]:
                try:
                    return self._import(item)
                except ImportError:
                    pass

            return self._import(path[-1])

        if not isinstance(path, string_types):
            return path

        if '.' not in path:
            raise ImportError("Cannot import %r. "
                              "Required format: [path/][package.]module.class. "
                              "Or choice from %r"
                              % (path, list(self.shortname_map)))

        if '/' in path:
            # This is dangerous, subject to race conditions, and
            # may not work properly for things like namespace packages
            import warnings
            warnings.warn("Absolute paths are deprecated and will be removed in 1.4."
                          "Please put the package on sys.path first",
                          DeprecationWarning)
            package_path, path = path.rsplit('/', 1)
            sys.path = [package_path] + sys.path
        else:
            package_path = None

        try:
            module, item = path.rsplit('.', 1)
            module = importlib.import_module(module)
            x = getattr(module, item, _NONE)
            if x is _NONE:
                raise ImportError('Cannot import %r from %r' % (item, module))
            return x
        finally:
            if package_path:
                try:
                    sys.path.remove(package_path)
                except ValueError: # pragma: no cover
                    pass

    shortname_map = {}

    def validate(self, value):
        if isinstance(value, type):
            return value
        return self._import([self.shortname_map.get(x, x) for x in value])


class Resolver(ImportableSetting, Setting):

    desc = """\
    The callable that will be used to create
    :attr:`gevent.hub.Hub.resolver`.

    See :doc:`dns` for more information.
    """

    default = [
        'thread',
        'dnspython',
        'ares',
        'block',
    ]

    shortname_map = {
        'ares': 'gevent.resolver.ares.Resolver',
        'thread': 'gevent.resolver.thread.Resolver',
        'block': 'gevent.resolver.blocking.Resolver',
        'dnspython': 'gevent.resolver.dnspython.Resolver',
    }



class Threadpool(ImportableSetting, Setting):

    desc = """\
    The kind of threadpool we use.
    """

    default = 'gevent.threadpool.ThreadPool'


class Loop(ImportableSetting, Setting):

    desc = """\
    The kind of the loop we use.

    """

    default = [
        'libev-cext',
        'libev-cffi',
        'libuv-cffi',
    ]

    shortname_map = {
        'libev-cext': 'gevent.libev.corecext.loop',
        'libev-cffi': 'gevent.libev.corecffi.loop',
        'libuv-cffi': 'gevent.libuv.loop.loop',
    }

    shortname_map['libuv'] = shortname_map['libuv-cffi']


class FormatContext(ImportableSetting, Setting):
    name = 'format_context'

    # using pprint.pformat can override custom __repr__ methods on dict/list
    # subclasses, which can be a security concern
    default = 'pprint.saferepr'


class LibevBackend(Setting):
    name = 'libev_backend'
    environment_key = 'GEVENT_BACKEND'

    desc = """\
    The backend for libev, such as 'select'
    """

    default = None

    validate = staticmethod(validate_anything)


class FileObject(ImportableSetting, Setting):
    desc = """\
    The kind of ``FileObject`` we will use.

    See :mod:`gevent.fileobject` for a detailed description.

    """
    environment_key = 'GEVENT_FILE'

    default = [
        'posix',
        'thread',
    ]

    shortname_map = {
        'thread': 'gevent._fileobjectcommon.FileObjectThread',
        'posix': 'gevent._fileobjectposix.FileObjectPosix',
        'block': 'gevent._fileobjectcommon.FileObjectBlock'
    }


class WatchChildren(Setting):
    desc = """\
    Should we *not* watch children with the event loop watchers?

    This is an advanced setting.

    See :mod:`gevent.os` for a detailed description.
    """
    name = 'disable_watch_children'
    environment_key = 'GEVENT_NOWAITPID'
    default = False

    validate = staticmethod(validate_bool)


class TraceMalloc(Setting):
    name = 'trace_malloc'
    environment_key = 'PYTHONTRACEMALLOC'
    default = False
    validate = staticmethod(validate_bool)

    desc = """\
    Should FFI objects track their allocation?

    This is only useful for low-level debugging.

    On Python 3, this environment variable is built in to the
    interpreter, and it may also be set with the ``-X
    tracemalloc`` command line argument.

    On Python 2, gevent interprets this argument and adds extra
    tracking information for FFI objects.
    """

# The ares settings are all interpreted by
# gevent/resolver/ares.pyx, so we don't do
# any validation here.

class AresSettingMixin(object):

    document = False

    @property
    def kwarg_name(self):
        return self.name[5:]

    validate = staticmethod(validate_anything)

    _convert = staticmethod(validate_anything)

class AresFlags(AresSettingMixin, Setting):
    name = 'ares_flags'
    default = None
    environment_key = 'GEVENTARES_FLAGS'

class AresTimeout(AresSettingMixin, Setting):
    document = True
    name = 'ares_timeout'
    default = None
    environment_key = 'GEVENTARES_TIMEOUT'
    desc = """\

    .. deprecated:: 1.3a2
       Prefer the :attr:`resolver_timeout` setting. If both are set,
       the results are not defined.
    """

class AresTries(AresSettingMixin, Setting):
    name = 'ares_tries'
    default = None
    environment_key = 'GEVENTARES_TRIES'

class AresNdots(AresSettingMixin, Setting):
    name = 'ares_ndots'
    default = None
    environment_key = 'GEVENTARES_NDOTS'

class AresUDPPort(AresSettingMixin, Setting):
    name = 'ares_udp_port'
    default = None
    environment_key = 'GEVENTARES_UDP_PORT'

class AresTCPPort(AresSettingMixin, Setting):
    name = 'ares_tcp_port'
    default = None
    environment_key = 'GEVENTARES_TCP_PORT'

class AresServers(AresSettingMixin, Setting):
    document = True
    name = 'ares_servers'
    default = None
    environment_key = 'GEVENTARES_SERVERS'
    desc = """\
    A list of strings giving the IP addresses of nameservers for the ares resolver.

    In the environment variable, these strings are separated by commas.

    .. deprecated:: 1.3a2
       Prefer the :attr:`resolver_nameservers` setting. If both are set,
       the results are not defined.
    """

# Generic nameservers, works for dnspython and ares.
class ResolverNameservers(AresSettingMixin, Setting):
    document = True
    name = 'resolver_nameservers'
    default = None
    environment_key = 'GEVENT_RESOLVER_NAMESERVERS'
    desc = """\
    A list of strings giving the IP addresses of nameservers for the (non-system) resolver.

    In the environment variable, these strings are separated by commas.

    .. rubric:: Resolver Behaviour

    * blocking

      Ignored

    * Threaded

      Ignored

    * dnspython

      If this setting is not given, the dnspython resolver will
      load nameservers to use from ``/etc/resolv.conf``
      or the Windows registry. This setting replaces any nameservers read
      from those means. Note that the file and registry are still read
      for other settings.

      .. caution:: dnspython does not validate the members of the list.
         An improper address (such as a hostname instead of IP) has
         undefined results, including hanging the process.

    * ares

      Similar to dnspython, but with more platform and compile-time
      options. ares validates that the members of the list are valid
      addresses.
    """

    # Normal string-to-list rules. But still validate_anything.
    _convert = Setting._convert

    # TODO: In the future, support reading a resolv.conf file
    # *other* than /etc/resolv.conf, and do that both on Windows
    # and other platforms. Also offer the option to disable the system
    # configuration entirely.

    @property
    def kwarg_name(self):
        return 'servers'

# Generic timeout, works for dnspython and ares
class ResolverTimeout(AresSettingMixin, Setting):
    document = True
    name = 'resolver_timeout'
    environment_key = 'GEVENT_RESOLVER_TIMEOUT'
    desc = """\
    The total amount of time that the DNS resolver will spend making queries.

    Only the ares and dnspython resolvers support this.

    .. versionadded:: 1.3a2
    """

    def _convert(self, value):
        if value:
            return float(value)

    @property
    def kwarg_name(self):
        return 'timeout'

config = Config()

# Go ahead and attempt to import the loop when this class is
# instantiated. The hub won't work if the loop can't be found. This
# can solve problems with the class being imported from multiple
# threads at once, leading to one of the imports failing.
# factories are themselves handled lazily. See #687.

# Don't cache it though, in case the user re-configures through the
# API.

try:
    Loop().get()
except ImportError: # pragma: no cover
    pass
