"""
RTNL protocol implementation
"""
import struct
import copy
import time

from socket import AF_INET
from pyroute2.arp import ARPHRD_VALUES
from pyroute2.common import map_namespace
from pyroute2.common import t_ip4ad
from pyroute2.common import t_ip6ad
from pyroute2.common import t_l2ad
from pyroute2.common import t_asciiz
from pyroute2.common import t_none
from pyroute2.common import t_uint8
from pyroute2.common import t_uint32
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import marshal

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


##
# RTNL-specific buffer reading "t_" routines
#
def t_state(buf, length):
    """
    Read 8 bit and return interface state as a string
    """
    return IF_OPER_VALUES[struct.unpack("=B", buf.read(1))[0]][8:]


class t_ifmap(nlmsg):
    """
    Interface map structure. This class can be used in
    the attribute mapping, since nlmsg supports this API.
    """
    fmt = "QQQHBB"
    fiels = ("mem_start", "mem_end", "base_addr", "irq", "dma", "port")


class ndmsg(nlmsg):
    fmt = "BiHBB"
    fields = ("family", "ifindex", "state", "flags", "ndm_type")

## neighbor attributes
NDA_UNSPEC = 0
NDA_DST = 1
NDA_LLADDR = 2
NDA_CACHEINFO = 3
NDA_PROBES = 4
(NDA_NAMES, NDA_VALUES) = map_namespace("NDA", globals())

t_nda_attr = {NDA_UNSPEC:    (t_none,    "none"),
              NDA_DST:       (t_ip4ad,   "dest"),
              NDA_LLADDR:    (t_l2ad,    "lladdr"),
              NDA_CACHEINFO: (t_none,    "cacheinfo"),
              NDA_PROBES:    (t_none,    "probes")}

t_nda6_attr = {NDA_UNSPEC:    (t_none,    "none"),
               NDA_DST:       (t_ip6ad,   "dest"),
               NDA_LLADDR:    (t_l2ad,    "lladdr"),
               NDA_CACHEINFO: (t_none,    "cacheinfo"),
               NDA_PROBES:    (t_none,    "probes")}


class ifinfmsg(nlmsg):
    fmt = "BHiII"
    fields = ("family", "ifi_type", "index", "flags", "change")

## link attributes
IFLA_UNSPEC = 0
IFLA_ADDRESS = 1
IFLA_BROADCAST = 2
IFLA_IFNAME = 3
IFLA_MTU = 4
IFLA_LINK = 5
IFLA_QDISC = 6
IFLA_STATS = 7
IFLA_COST = 8
IFLA_PRIORITY = 9
IFLA_MASTER = 10
IFLA_WIRELESS = 11  # Wireless Extension event - see iproute2:wireless.h
IFLA_PROTINFO = 12  # Protocol specific information for a link
IFLA_TXQLEN = 13
IFLA_MAP = 14
IFLA_WEIGHT = 15
IFLA_OPERSTATE = 16
IFLA_LINKMODE = 17

IF_OPER_UNKNOWN = 0
IF_OPER_NOTPRESENT = 1
IF_OPER_DOWN = 2
IF_OPER_LOWERLAYERDOWN = 3
IF_OPER_TESTING = 4
IF_OPER_DORMANT = 5
IF_OPER_UP = 6

(IF_OPER_NAMES, IF_OPER_VALUES) = map_namespace("IF_OPER", globals())
(IFLA_NAMES, IFLA_VALUES) = map_namespace("IFLA", globals())


t_ifla_attr = {IFLA_UNSPEC:    (t_none,        "none"),
               IFLA_ADDRESS:   (t_l2ad,        "hwaddr"),
               IFLA_BROADCAST: (t_l2ad,        "broadcast"),
               IFLA_IFNAME:    (t_asciiz,      "dev"),
               IFLA_MTU:       (t_uint32,      "mtu"),
               IFLA_LINK:      (t_uint32,      "link"),
               IFLA_QDISC:     (t_asciiz,      "qdisc"),
               IFLA_STATS:     (t_none,        "stats"),
               IFLA_OPERSTATE: (t_state,       "state"),
               IFLA_TXQLEN:    (t_uint32,      "txqlen"),
               IFLA_LINKMODE:  (t_uint8,       "linkmode"),
               IFLA_MAP:       (t_ifmap,       "ifmap")}


## netdevice flags
iff = {}
iff["UP"] = 0x1    # interface is up
iff["BROADCAST"] = 0x2    # broadcast address valid
iff["DEBUG"] = 0x4    # turn on debugging
iff["LOOPBACK"] = 0x8    # is a loopback net
iff["POINTOPOINT"] = 0x10    # interface is has p-p link
iff["NOTRAILERS"] = 0x20    # avoid use of trailers
iff["RUNNING"] = 0x40    # resources allocated
iff["NOARP"] = 0x80    # no ARP protocol
iff["PROMISC"] = 0x100    # receive all packets
iff["ALLMULTI"] = 0x200    # receive all multicast packets
iff["MASTER"] = 0x400    # master of a load balancer
iff["SLAVE"] = 0x800    # slave of a load balancer
iff["MULTICAST"] = 0x1000  # supports multicast
iff["PORTSEL"] = 0x2000  # can set media type
iff["AUTOMEDIA"] = 0x4000  # auto media select active
iff["DYNAMIC"] = 0x8000  # dialup device with changing addresses


class ifaddrmsg(nlmsg):
    fmt = "BBBBI"
    fields = ("family", "prefixlen", "flags", "scope", "index")

## address attributes
#
# Important comment:
# IFA_ADDRESS is prefix address, rather than local interface address.
# It makes no difference for normally configured broadcast interfaces,
# but for point-to-point IFA_ADDRESS is DESTINATION address,
# local address is supplied in IFA_LOCAL attribute.
#
IFA_UNSPEC = 0
IFA_ADDRESS = 1
IFA_LOCAL = 2
IFA_LABEL = 3
IFA_BROADCAST = 4
IFA_ANYCAST = 5
IFA_CACHEINFO = 6
IFA_MULTICAST = 7
(IFA_NAMES, IFA_VALUES) = map_namespace("IFA_", globals())

t_ifa_attr = {IFA_UNSPEC:     (t_none,    "none"),
              IFA_ADDRESS:    (t_ip4ad,   "address"),
              IFA_LOCAL:      (t_ip4ad,   "local"),
              IFA_LABEL:      (t_asciiz,  "dev"),
              IFA_BROADCAST:  (t_ip4ad,   "broadcast"),
              IFA_ANYCAST:    (t_ip4ad,   "anycast"),
              IFA_CACHEINFO:  (t_none,    "cacheinfo"),
              IFA_MULTICAST:  (t_ip4ad,   "multycast")}


t_ifa6_attr = {IFA_UNSPEC:     (t_none,    "none"),
               IFA_ADDRESS:    (t_ip6ad,   "address"),
               IFA_LABEL:      (t_asciiz,  "dev"),
               IFA_CACHEINFO:  (t_none,    "cacheinfo")}


class rtmsg(nlmsg):
    fmt = "BBBBBBBBI"
    fields = ("family", "dst_len", "src_len", "tos", "table",
              "proto", "scope", "type", "flags")

## route attributes
RTA_UNSPEC = 0
RTA_DST = 1
RTA_SRC = 2
RTA_IIF = 3
RTA_OIF = 4
RTA_GATEWAY = 5
RTA_PRIORITY = 6
RTA_PREFSRC = 7
RTA_METRICS = 8
RTA_MULTIPATH = 9
RTA_PROTOINFO = 10
RTA_FLOW = 11
RTA_CACHEINFO = 12  # FIXME: kernel://include/linux/rtnetlink.h:320,
                    # struct rta_cacheinfo
RTA_SESSION = 13
RTA_MP_ALGO = 14    # no longer used
RTA_TABLE = 15

(RTA_NAMES, RTA_VALUES) = map_namespace("RTA", globals())


## rtmsg.type
RTN_UNSPEC = 0
RTN_UNICAST = 1    # Gateway or direct route
RTN_LOCAL = 2    # Accept locally
RTN_BROADCAST = 3    # Accept locally as broadcast, send as broadcast
RTN_ANYCAST = 4    # Accept locally as broadcast, but send as unicast
RTN_MULTICAST = 5    # Multicast route
RTN_BLACKHOLE = 6    # Drop
RTN_UNREACHABLE = 7    # Destination is unreachable
RTN_PROHIBIT = 8    # Administratively prohibited
RTN_THROW = 9    # Not in this table
RTN_NAT = 10    # Translate this address
RTN_XRESOLVE = 11    # Use external resolver

## rtmsg.proto
RTPROT_UNSPEC = 0
RTPROT_REDIRECT = 1  # Route installed by ICMP redirects;
                     # not used by current IPv4
RTPROT_KERNEL = 2    # Route installed by kernel
RTPROT_BOOT = 3    # Route installed during boot
RTPROT_STATIC = 4    # Route installed by administrator
# Values of protocol >= RTPROT_STATIC are not interpreted by kernel;
# they are just passed from user and back as is.
# It will be used by hypothetical multiple routing daemons.
# Note that protocol values should be standardized in order to
# avoid conflicts.
RTPROT_GATED = 8    # Apparently, GateD
RTPROT_RA = 9    # RDISC/ND router advertisements
RTPROT_MRT = 10    # Merit MRT
RTPROT_ZEBRA = 11    # Zebra
RTPROT_BIRD = 12    # BIRD
RTPROT_DNROUTED = 13    # DECnet routing daemon
RTPROT_XORP = 14    # XORP
RTPROT_NTK = 15    # Netsukuku

## rtmsg.scope
RT_SCOPE_UNIVERSE = 0
# User defined values
RT_SCOPE_SITE = 200
RT_SCOPE_LINK = 253
RT_SCOPE_HOST = 254
RT_SCOPE_NOWHERE = 255

## rtmsg.flags
RTM_F_NOTIFY = 0x100    # Notify user of route change
RTM_F_CLONED = 0x200    # This route is cloned
RTM_F_EQUALIZE = 0x400    # Multipath equalizer: NI
RTM_F_PREFIX = 0x800    # Prefix addresses
t_rta_attr = {RTA_UNSPEC:    (t_none,    "none"),
              RTA_DST:       (t_ip4ad,   "dst_prefix"),
              RTA_SRC:       (t_ip4ad,   "src_prefix"),
              RTA_IIF:       (t_uint32,  "input_link"),
              RTA_OIF:       (t_uint32,  "output_link"),
              RTA_GATEWAY:   (t_ip4ad,   "gateway"),
              RTA_PRIORITY:  (t_uint32,  "priority"),
              RTA_PREFSRC:   (t_ip4ad,   "prefsrc"),
              RTA_METRICS:   (t_uint32,  "metric"),
              RTA_MULTIPATH: (t_none,    "mp"),
              RTA_PROTOINFO: (t_none,    "protoinfo"),
              RTA_FLOW:      (t_none,    "flow"),
              RTA_CACHEINFO: (t_none,    "cacheinfo"),
              RTA_SESSION:   (t_none,    "session"),
              RTA_MP_ALGO:   (t_none,    "mp_algo"),  # no longer used
              RTA_TABLE:     (t_uint32,  "table")}

t_rta6_attr = {RTA_UNSPEC:    (t_none,    "none"),
               RTA_DST:       (t_ip6ad,   "dst_prefix"),
               RTA_SRC:       (t_ip6ad,   "src_prefix"),
               RTA_IIF:       (t_uint32,  "input_link"),
               RTA_OIF:       (t_uint32,  "output_link"),
               RTA_GATEWAY:   (t_ip6ad,   "gateway"),
               RTA_PRIORITY:  (t_uint32,  "priority"),
               RTA_PREFSRC:   (t_ip6ad,   "prefsrc"),
               RTA_METRICS:   (t_uint32,  "metric"),
               RTA_MULTIPATH: (t_none,    "mp"),
               RTA_PROTOINFO: (t_none,    "protoinfo"),
               RTA_FLOW:      (t_none,    "flow"),
               RTA_CACHEINFO: (t_none,    "cacheinfo"),
               RTA_SESSION:   (t_none,    "session"),
               RTA_MP_ALGO:   (t_none,    "mp_algo"),  # no longer used
               RTA_TABLE:     (t_uint32,  "table")}


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
