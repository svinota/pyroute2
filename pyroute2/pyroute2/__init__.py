##
#
# This module contains all the public symbols from the library.
#
import sys
import struct

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
    import win_inet_pton            # noqa: F401

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
for entry_point in metadata.entry_points().get('pr2modules', []):
    globals()[entry_point.name] = entry_point.load()
    modules.append(entry_point.name)

__all__ = []
__all__.extend(modules)
