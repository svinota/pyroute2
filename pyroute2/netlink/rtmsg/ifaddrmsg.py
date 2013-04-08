
from pyroute2.common import map_namespace
from pyroute2.common import t_ip4ad
from pyroute2.common import t_ip6ad
from pyroute2.common import t_asciiz
from pyroute2.common import t_none
from pyroute2.netlink.generic import nlmsg


class ifaddrmsg(nlmsg):
    """
    IP address information

    struct ifaddrmsg {
       unsigned char ifa_family;    /* Address type */
       unsigned char ifa_prefixlen; /* Prefixlength of address */
       unsigned char ifa_flags;     /* Address flags */
       unsigned char ifa_scope;     /* Address scope */
       int           ifa_index;     /* Interface index */
    };

    """
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
