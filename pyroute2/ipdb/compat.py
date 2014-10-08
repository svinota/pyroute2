'''
This module has nothing to do with Netlink in any form. It
provides compatibility functions to run IPDB on ancient
and pre-historical platforms like RHEL 6.5
'''
import time
import platform
from pyroute2.netlink import NetlinkError
_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'
_ANCIENT_BARRIER = 0.3
_ANCIENT_PLATFORM = (platform.dist()[0] in ('redhat', 'centos') and
                     platform.dist()[1].startswith('6.'))


#
#
#
def bypass(f):
    if _ANCIENT_PLATFORM:
        return f
    else:
        def _bypass(*argv, **kwarg):
            pass
        return _bypass


def replace(r):
    def decorator(f):
        if _ANCIENT_PLATFORM:
            return f
        else:
            return r
    return decorator


@bypass
def fix_timeout(timeout):
    time.sleep(timeout)


@bypass
def fix_check_link(nl, index):
    # check, if the link really exits --
    # on some old kernels you can receive
    # broadcast RTM_NEWLINK after the link
    # was deleted
    try:
        nl.get_links(index)
    except NetlinkError as e:
        if e.code == 19:  # No such device
            # just drop this message then
            return True

#
# Utility functions to call external programs or set up
# network objects w/o RT netlink, e.g. via sysfs
#
