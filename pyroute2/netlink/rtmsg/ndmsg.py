
from pyroute2.netlink.generic import nlmsg


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

    fields = ("family",
              "ifindex",
              "state",
              "flags",
              "ndm_type")

    # Please note, that nla_map creates implicit
    # enumeration. In this case it will be:
    #
    # NDA_UNSPEC = 0
    # NDA_DST = 1
    # NDA_LLADDR = 2
    # NDA_CACHEINFO = 3
    # NDA_PROBES = 4
    #
    nla_map = (('NDA_UNSPEC', 'hex'),
               ('NDA_DST', 'ipaddr'),
               ('NDA_LLADDR', 'l2addr'),
               ('NDA_CACHEINFO', 'hex'),
               ('NDA_PROBES', 'hex'))
