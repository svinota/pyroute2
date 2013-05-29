
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla


class ndmsg(nlmsg):
    '''
    ARP cache update message

    struct ndmsg {
        unsigned char ndm_family;
        int           ndm_ifindex;  /* Interface index */
        __u16         ndm_state;    /* State */
        __u8          ndm_flags;    /* Flags */
        __u8          ndm_type;
    };

    struct nda_cacheinfo {
        __u32         ndm_confirmed;
        __u32         ndm_used;
        __u32         ndm_updated;
        __u32         ndm_refcnt;
    };
    '''
    fields = (('family', 'B'),
              ('ifindex', 'i'),
              ('state', 'H'),
              ('flags', 'B'),
              ('ndm_type', 'B'))

    # Please note, that nla_map creates implicit
    # enumeration. In this case it will be:
    #
    # NDA_UNSPEC = 0
    # NDA_DST = 1
    # NDA_LLADDR = 2
    # NDA_CACHEINFO = 3
    # NDA_PROBES = 4
    #
    nla_map = (('NDA_UNSPEC', 'none'),
               ('NDA_DST', 'ipaddr'),
               ('NDA_LLADDR', 'l2addr'),
               ('NDA_CACHEINFO', 'cacheinfo'),
               ('NDA_PROBES', 'uint32'))

    class cacheinfo(nla):
        fields = (('ndm_confirmed', 'I'),
                  ('ndm_used', 'I'),
                  ('ndm_updated', 'I'),
                  ('ndm_refcnt', 'I'))
