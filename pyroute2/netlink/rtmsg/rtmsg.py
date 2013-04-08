
from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import t_ip4ad
from pyroute2.common import t_ip6ad
from pyroute2.common import t_none
from pyroute2.common import t_uint32
from pyroute2.netlink.generic import nlmsg


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


class rtmsg(nlmsg):
    """
    Routing update message

    struct rtmsg {
        unsigned char rtm_family;   /* Address family of route */
        unsigned char rtm_dst_len;  /* Length of destination */
        unsigned char rtm_src_len;  /* Length of source */
        unsigned char rtm_tos;      /* TOS filter */

        unsigned char rtm_table;    /* Routing table ID */
        unsigned char rtm_protocol; /* Routing protocol; see below */
        unsigned char rtm_scope;    /* See below */
        unsigned char rtm_type;     /* See below */

        unsigned int  rtm_flags;
    };
    """
    fmt = "BBBBBBBBI"
    fields = ("family", "dst_len", "src_len", "tos", "table",
              "proto", "scope", "type", "flags")
    attr_map = None

    def setup(self):
        self['type'] = 'route'
        if self['family'] == AF_INET:
            self.attr_map = t_rta_attr
        elif self['family'] == AF_INET6:
            self.attr_map = t_rta6_attr
