##
#
# NB: the deferred import code may be removed
#
# That should not affect neither the public API, nor the
# type matching with isinstance() and issubclass()
#
import sys
import struct
import logging
from pyroute2.ipdb.exceptions import (DeprecationException,
                                      CommitException,
                                      CreateException,
                                      PartialCommitException)
from pyroute2.netlink.exceptions import (NetlinkError,
                                         NetlinkDecodeError)
from pyroute2.netlink.rtnl.req import (IPRouteRequest,
                                       IPLinkRequest)
from pyroute2.iproute import (IPRoute,
                              IPBatch,
                              RawIPRoute)
from pyroute2.ipset import IPSet
from pyroute2.ipdb.main import IPDB
from pyroute2.iwutil import IW
from pyroute2.devlink import DL
from pyroute2.conntrack import Conntrack
from pyroute2.nftables.main import NFTables
from pyroute2.netns.nslink import NetNS
from pyroute2.netns.process.proxy import NSPopen
from pyroute2.netlink.rtnl.iprsocket import IPRSocket
from pyroute2.netlink.taskstats import TaskStats
from pyroute2.netlink.nl80211 import NL80211
from pyroute2.netlink.devlink import DevlinkSocket
from pyroute2.netlink.event.acpi_event import AcpiEventSocket
from pyroute2.netlink.event.dquot import DQuotSocket
from pyroute2.netlink.ipq import IPQSocket
from pyroute2.netlink.diag import DiagSocket
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.nfnetlink.nftsocket import NFTSocket
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTSocket
#
# The Console class is a bit special, it tries to engage
# modules from stdlib, that are sometimes stripped. Some
# of them are optional, but some aren't. So catch possible
# errors here.
try:
    from pyroute2.cli import Console
    HAS_CONSOLE = True
except ImportError:
    HAS_CONSOLE = False


log = logging.getLogger(__name__)
# Add a NullHandler to the library's top-level logger to avoid complaints
# on logging calls when no handler is configured.
# see https://docs.python.org/2/howto/logging.html#library-config
if sys.version_info >= (2, 7):  # This is only available from 2.7 onwards
    log.addHandler(logging.NullHandler())

try:
    # probe, if the bytearray can be used in struct.unpack_from()
    struct.unpack_from('I', bytearray((1, 0, 0, 0)), 0)
except:
    if sys.version_info[0] < 3:
        # monkeypatch for old Python versions
        log.warning('patching struct.unpack_from()')

        def wrapped(fmt, buf, offset=0):
            return struct._u_f_orig(fmt, str(buf), offset)
        struct._u_f_orig = struct.unpack_from
        struct.unpack_from = wrapped
    else:
        raise

# reexport exceptions
exceptions = [NetlinkError,
              NetlinkDecodeError,
              DeprecationException,
              CommitException,
              CreateException,
              PartialCommitException]

# reexport classes
classes = [IPRouteRequest,
           IPLinkRequest,
           IPRoute,
           IPBatch,
           RawIPRoute,
           IPSet,
           IPDB,
           IW,
           DL,
           Conntrack,
           NFTables,
           NetNS,
           NSPopen,
           IPRSocket,
           TaskStats,
           NL80211,
           DevlinkSocket,
           AcpiEventSocket,
           DQuotSocket,
           IPQSocket,
           DiagSocket,
           GenericNetlinkSocket,
           NFTSocket,
           NFCTSocket]

if HAS_CONSOLE:
    classes.append(Console)
else:
    log.warning("Couldn't import the Console class")

__all__ = []


class __common(object):
    def __getattribute__(self, key):
        log.warning('module pyroute2.ipdb.common is deprecated, '
                    'use pyroute2.ipdb.exceptions instead')
        return getattr(globals()['ipdb'].exceptions, key)


globals()['ipdb'].common = __common()

__all__.extend([x.__name__ for x in exceptions])
__all__.extend([x.__name__ for x in classes])
