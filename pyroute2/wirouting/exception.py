"""
Exceptions used by the wirouting subpackage
"""

import errno
from typing import Dict, Type

from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.rtnl import (
    RTM_GETLINK,
    RTM_NEWLINK,
    RTM_NEWLINKPROP,
    RTM_SETLINK,
)


class InterfaceDoesNotExist(NetlinkError):
    """Requested interface does not exist"""


class InterfaceExists(NetlinkError):
    """Creation failed since interface already exists"""


class NotPhyDevice(NetlinkError):
    """Device is not a physical interface"""


exception_map: Dict[int, Dict[int, Type[Exception]]] = {
    RTM_NEWLINK: {
        errno.EEXIST: InterfaceExists,
        errno.ENODEV: InterfaceDoesNotExist,
    },
    RTM_NEWLINKPROP: {errno.ENODEV: InterfaceDoesNotExist},
    RTM_GETLINK: {errno.ENODEV: InterfaceDoesNotExist},
    RTM_SETLINK: {
        errno.EEXIST: InterfaceExists,
        errno.ENODEV: InterfaceDoesNotExist,
    },
}


def exception_factory(err, msg):
    try:
        return exception_map[msg.orig_type][err.code](*err.args)
    except LookupError:
        return err
