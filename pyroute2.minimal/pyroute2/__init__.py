##
#
# This module contains all the public symbols from the library.
#
import sys
import struct
import importlib

##
#
# Version
#
try:
    from pr2modules.config.version import __version__
except ImportError:
    __version__ = 'unknown'

##
#
# Windows platform specific: socket module monkey patching
#
# To use the library on Windows, run::
#   pip install win-inet-pton
#
if sys.platform.startswith('win'):  # noqa: E402
    import win_inet_pton  # noqa: F401

##
#
# Logging setup
#
# See the history:
#  * https://github.com/svinota/pyroute2/issues/246
#  * https://github.com/svinota/pyroute2/issues/255
#  * https://github.com/svinota/pyroute2/issues/270
#  * https://github.com/svinota/pyroute2/issues/573
#  * https://github.com/svinota/pyroute2/issues/601
#
from pr2modules.config import log

#
#
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata


try:
    # probe, if the bytearray can be used in struct.unpack_from()
    struct.unpack_from('I', bytearray((1, 0, 0, 0)), 0)
except Exception:
    if sys.version_info[0] < 3:
        # monkeypatch for old Python versions
        log.warning('patching struct.unpack_from()')

        def wrapped(fmt, buf, offset=0):
            return struct._u_f_orig(fmt, str(buf), offset)

        struct._u_f_orig = struct.unpack_from
        struct.unpack_from = wrapped
    else:
        raise


# load entry_points
modules = []
namespace_inject = {}
for entry_point in metadata.entry_points().get('pr2modules', []):
    globals()[entry_point.name] = loaded = entry_point.load()
    modules.append(entry_point.name)
    if len(entry_point.value.split(':')) == 1:
        key = 'pyroute2.%s' % entry_point.name
        namespace_inject[key] = loaded

__all__ = []
__all__.extend(modules)


class PyRoute2ModuleSpec(importlib.machinery.ModuleSpec):
    def __init__(
        self,
        name,
        loader,
        *argv,
        origin=None,
        loader_state=None,
        is_package=None
    ):
        self.name = name
        self.loader = loader
        self.origin = None
        self.submodule_search_locations = None
        self.loader_state = None
        self.cached = None
        self.has_location = False


class PyRoute2ModuleFinder(importlib.abc.MetaPathFinder):
    @staticmethod
    def find_spec(fullname, path, target=None):
        if target is not None:
            return None
        if fullname not in namespace_inject:
            return None
        return PyRoute2ModuleSpec(fullname, PyRoute2ModuleFinder)

    @staticmethod
    def create_module(spec):
        if spec.name not in namespace_inject:
            return None
        return namespace_inject[spec.name]

    @staticmethod
    def exec_module(spec):
        pass


sys.meta_path.append(PyRoute2ModuleFinder())
