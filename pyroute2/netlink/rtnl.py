"""
RTNL protocol implementation
"""
import copy
import time

from socket import AF_INET
from pyroute2.arp import ARPHRD_VALUES
from pyroute2.common import map_namespace
from pyroute2.netlink.generic import marshal
# link messages
from pyroute2.netlink.rtmsg.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtmsg.ifinfmsg import t_ifla_attr
# address messages
from pyroute2.netlink.rtmsg.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtmsg.ifaddrmsg import t_ifa_attr
from pyroute2.netlink.rtmsg.ifaddrmsg import t_ifa6_attr
# route messages
from pyroute2.netlink.rtmsg.rtmsg import rtmsg
from pyroute2.netlink.rtmsg.rtmsg import t_rta_attr
from pyroute2.netlink.rtmsg.rtmsg import t_rta6_attr
# arp cache messages
from pyroute2.netlink.rtmsg.ndmsg import ndmsg
from pyroute2.netlink.rtmsg.ndmsg import t_nda_attr
from pyroute2.netlink.rtmsg.ndmsg import t_nda6_attr

##  RTnetlink multicast groups
RTNLGRP_NONE = 0x0
RTNLGRP_LINK = 0x1
RTNLGRP_NOTIFY = 0x2
RTNLGRP_NEIGH = 0x4
RTNLGRP_TC = 0x8
RTNLGRP_IPV4_IFADDR = 0x10
RTNLGRP_IPV4_MROUTE = 0x20
RTNLGRP_IPV4_ROUTE = 0x40
RTNLGRP_IPV4_RULE = 0x80
RTNLGRP_IPV6_IFADDR = 0x100
RTNLGRP_IPV6_MROUTE = 0x200
RTNLGRP_IPV6_ROUTE = 0x400
RTNLGRP_IPV6_IFINFO = 0x800
RTNLGRP_DECnet_IFADDR = 0x1000
RTNLGRP_NOP2 = 0x2000
RTNLGRP_DECnet_ROUTE = 0x4000
RTNLGRP_DECnet_RULE = 0x8000
RTNLGRP_NOP4 = 0x10000
RTNLGRP_IPV6_PREFIX = 0x20000
RTNLGRP_IPV6_RULE = 0x40000
(RTNLGRP_NAMES, RTNLGRP_VALUES) = map_namespace("RTNLGRP", globals())

## Types of messages
#RTM_BASE = 16
RTM_NEWLINK = 16
RTM_DELLINK = 17
RTM_GETLINK = 18
RTM_SETLINK = 19
RTM_NEWADDR = 20
RTM_DELADDR = 21
RTM_GETADDR = 22
RTM_NEWROUTE = 24
RTM_DELROUTE = 25
RTM_GETROUTE = 26
RTM_NEWNEIGH = 28
RTM_DELNEIGH = 29
RTM_GETNEIGH = 30
RTM_NEWRULE = 32
RTM_DELRULE = 33
RTM_GETRULE = 34
RTM_NEWQDISC = 36
RTM_DELQDISC = 37
RTM_GETQDISC = 38
RTM_NEWTCLASS = 40
RTM_DELTCLASS = 41
RTM_GETTCLASS = 42
RTM_NEWTFILTER = 44
RTM_DELTFILTER = 45
RTM_GETTFILTER = 46
RTM_NEWACTION = 48
RTM_DELACTION = 49
RTM_GETACTION = 50
RTM_NEWPREFIX = 52
RTM_GETMULTICAST = 58
RTM_GETANYCAST = 62
RTM_NEWNEIGHTBL = 64
RTM_GETNEIGHTBL = 66
RTM_SETNEIGHTBL = 67
(RTM_NAMES, RTM_VALUES) = map_namespace("RTM", globals())


class marshal_rtnl(marshal):

    def __init__(self, sock=None):
        marshal.__init__(self, sock)
        self.reverse = RTM_VALUES

    def parse(self):
        event = {"attributes": [],
                 "unparsed": [],
                 "header": copy.copy(self.header)}
        if self.debug:
            event["header"] = copy.copy(self.header)
            event["header"]["msg_hex"] = self.msg_hex
            event["header"]["timestamp"] = time.asctime()
        attr_map = {}
        if self.header['type'] <= RTM_DELLINK:
            event.update(ifinfmsg(self.buf))
            event['ifi_type'] = ARPHRD_VALUES[event['ifi_type']][7:]
            event['type'] = 'link'
            attr_map = t_ifla_attr
        elif self.header['type'] <= RTM_DELADDR:
            event.update(ifaddrmsg(self.buf))
            event['type'] = 'addr'
            if event['family'] == AF_INET:
                attr_map = t_ifa_attr
            else:
                attr_map = t_ifa6_attr
        elif self.header['type'] <= RTM_DELROUTE:
            event.update(rtmsg(self.buf))
            event['type'] = 'route'
            if event['family'] == AF_INET:
                attr_map = t_rta_attr
            else:
                attr_map = t_rta6_attr
        elif self.header['type'] <= RTM_GETNEIGH:
            event.update(ndmsg(self.buf))
            event['type'] = 'neigh'
            if event['family'] == AF_INET:
                attr_map = t_nda_attr
            else:
                attr_map = t_nda6_attr
        else:
            pass
        for i in self.get_next_attr(attr_map):
            if type(i[0]) is str:
                event["attributes"].append(i)
            else:
                event["unparsed"].append(i)

        return event
