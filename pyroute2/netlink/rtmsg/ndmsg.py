
from socket import AF_INET
from socket import AF_INET6
from socket import AF_BRIDGE
from pyroute2.common import t_hex
from pyroute2.common import t_ip4ad
from pyroute2.common import t_ip6ad
from pyroute2.common import t_l2ad
from pyroute2.common import t_none
from pyroute2.netlink.generic import nlmsg


## neighbor attributes
NDA_UNSPEC = 0
NDA_DST = 1
NDA_LLADDR = 2
NDA_CACHEINFO = 3
NDA_PROBES = 4

t_nda_attr = {NDA_UNSPEC:    (t_none,    "none"),
              NDA_DST:       (t_ip4ad,   "dest"),
              NDA_LLADDR:    (t_l2ad,    "lladdr"),
              NDA_CACHEINFO: (t_hex,    "cacheinfo"),
              NDA_PROBES:    (t_hex,    "probes")}

t_nda6_attr = {NDA_UNSPEC:    (t_none,    "none"),
               NDA_DST:       (t_ip6ad,   "dest"),
               NDA_LLADDR:    (t_l2ad,    "lladdr"),
               NDA_CACHEINFO: (t_hex,    "cacheinfo"),
               NDA_PROBES:    (t_hex,    "probes")}


class ndmsg(nlmsg):
    """
    ARP cache update message

    struct ndmsg {
        unsigned char ndm_family;
        int           ndm_ifindex;  /* Interface index */
        __u16         ndm_state;    /* State */
        __u8          ndm_flags;    /* Flags */
        __u8          ndm_type;
    };

    TODO:
    struct nda_cacheinfo {
        __u32         ndm_confirmed;
        __u32         ndm_used;
        __u32         ndm_updated;
        __u32         ndm_refcnt;
    };
    """
    fmt = "BiHBB"
    fields = ("family", "ifindex", "state", "flags", "ndm_type")
    attr_map = None

    def setup(self):
        self['type'] = 'neigh'
        if self['family'] == AF_INET:
            self.attr_map = t_nda_attr
        elif self['family'] == AF_INET6:
            self.attr_map = t_nda6_attr
        elif self['family'] == AF_BRIDGE:
            self.attr_map = t_nda_attr
        else:
            raise Exception("Bad protocol %s in ndmsg" % (self['family']))
