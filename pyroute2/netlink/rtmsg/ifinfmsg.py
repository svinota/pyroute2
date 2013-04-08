import struct

from pyroute2.arp import ARPHRD_VALUES
from pyroute2.common import map_namespace
from pyroute2.common import t_l2ad
from pyroute2.common import t_asciiz
from pyroute2.common import t_none
from pyroute2.common import t_uint8
from pyroute2.common import t_uint32
from pyroute2.netlink.generic import nlmsg


##
# ifinfmsg-specific buffer reading "t_" routines
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


class ifinfmsg(nlmsg):
    """
    Network interface message
    struct ifinfomsg {
        unsigned char  ifi_family; /* AF_UNSPEC */
        unsigned short ifi_type;   /* Device type */
        int            ifi_index;  /* Interface index */
        unsigned int   ifi_flags;  /* Device flags  */
        unsigned int   ifi_change; /* change mask */
    };
    """
    fmt = "BHiII"
    fields = ("family", "ifi_type", "index", "flags", "change")

    def setup(self):
        self['type'] = 'link'
        self['ifi_type'] = ARPHRD_VALUES[self['ifi_type']][7:]
        self.attr_map = t_ifla_attr
