##
#
# This module contains all the public symbols from the library.
#

##
#
# Version
#
try:
    from pyroute2.config.version import __version__
except ImportError:
    __version__ = 'unknown'
import sys

from pyroute2.cli.console import Console
from pyroute2.cli.server import Server

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
from pyroute2.config import log
from pyroute2.conntrack import Conntrack, ConntrackEntry
from pyroute2.devlink import DL
from pyroute2.ethtool.ethtool import Ethtool
from pyroute2.ipdb import IPDB, CommitException, CreateException
from pyroute2.iproute import (
    AsyncIPRoute,
    ChaoticIPRoute,
    IPBatch,
    IPRoute,
    NetNS,
    RawIPRoute,
)
from pyroute2.ipset import IPSet
from pyroute2.ipvs import IPVS, IPVSDest, IPVSService
from pyroute2.iwutil import IW
from pyroute2.ndb.main import NDB
from pyroute2.netlink.connector.cn_proc import ProcEventSocket
from pyroute2.netlink.devlink import DevlinkSocket
from pyroute2.netlink.diag import DiagSocket, ss2
from pyroute2.netlink.event.acpi_event import AcpiEventSocket
from pyroute2.netlink.event.dquot import DQuotSocket
from pyroute2.netlink.exceptions import (
    ChaoticException,
    NetlinkDecodeError,
    NetlinkDumpInterrupted,
    NetlinkError,
)
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.generic.l2tp import L2tp
from pyroute2.netlink.generic.mptcp import MPTCP
from pyroute2.netlink.generic.wireguard import WireGuard
from pyroute2.netlink.ipq import IPQSocket
from pyroute2.netlink.nfnetlink.nfctsocket import NFCTSocket
from pyroute2.netlink.nfnetlink.nftsocket import AsyncNFTSocket, NFTSocket
from pyroute2.netlink.nl80211 import NL80211
from pyroute2.netlink.rtnl.iprsocket import AsyncIPRSocket, IPRSocket
from pyroute2.netlink.taskstats import TaskStats
from pyroute2.netlink.uevent import UeventSocket
from pyroute2.nslink.nspopen import NSPopen
from pyroute2.plan9.client import Plan9ClientSocket
from pyroute2.plan9.server import Plan9ServerSocket
from pyroute2.wiset import WiSet

##
#
# Windows platform specific: socket module monkey patching
#
# To use the library on Windows, run::
#   pip install win-inet-pton
#
if sys.platform.startswith('win'):  # noqa: E402
    import win_inet_pton  # noqa: F401


modules = [
    AcpiEventSocket,
    AsyncIPRoute,
    AsyncIPRSocket,
    AsyncNFTSocket,
    ChaoticException,
    ChaoticIPRoute,
    CommitException,
    Conntrack,
    ConntrackEntry,
    Console,
    CreateException,
    DevlinkSocket,
    DiagSocket,
    DL,
    DQuotSocket,
    Ethtool,
    IPBatch,
    IPDB,
    IPQSocket,
    IPRoute,
    IPRSocket,
    IPSet,
    IPVS,
    IPVSDest,
    IPVSService,
    IW,
    GenericNetlinkSocket,
    L2tp,
    MPTCP,
    NDB,
    NetlinkError,
    NetlinkDecodeError,
    NetlinkDumpInterrupted,
    NetNS,
    NFCTSocket,
    NFTSocket,
    NL80211,
    NSPopen,
    Plan9ClientSocket,
    Plan9ServerSocket,
    ProcEventSocket,
    RawIPRoute,
    Server,
    ss2,
    TaskStats,
    UeventSocket,
    WireGuard,
    WiSet,
    log,
]

__all__ = []
__all__.extend(modules)
