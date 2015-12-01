from pyroute2.common import map_namespace
from pyroute2.netlink import nlmsg
from pyroute2.netlink import nla


NUD_INCOMPLETE = 0x01
NUD_REACHABLE = 0x02
NUD_STALE = 0x04
NUD_DELAY = 0x08
NUD_PROBE = 0x10
NUD_FAILED = 0x20

# dummy states

NUD_NOARP = 0x40
NUD_PERMANENT = 0x80
NUD_NONE = 0x00

(NUD_NAMES, NUD_VALUES) = map_namespace('NUD_', globals())


class ndmsg(nlmsg):
    '''
    ARP cache update message

    C structure::

        struct ndmsg {
            unsigned char ndm_family;
            int           ndm_ifindex;  /* Interface index */
            __u16         ndm_state;    /* State */
            __u8          ndm_flags;    /* Flags */
            __u8          ndm_type;
        };

    Cache info structure::

        struct nda_cacheinfo {
            __u32         ndm_confirmed;
            __u32         ndm_used;
            __u32         ndm_updated;
            __u32         ndm_refcnt;
        };
    '''
    prefix = 'NDA_'

    fields = (('family', 'B'),
              ('__pad', '3x'),
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
    # ...
    #
    nla_map = (('NDA_UNSPEC', 'none'),
               ('NDA_DST', 'ipaddr'),
               ('NDA_LLADDR', 'l2addr'),
               ('NDA_CACHEINFO', 'cacheinfo'),
               ('NDA_PROBES', 'uint32'),
               ('NDA_VLAN', 'uint16'),
               ('NDA_PORT', 'be16'),
               ('NDA_VNI', 'be32'),
               ('NDA_IFINDEX', 'uint32'),
               ('NDA_MASTER', 'uint32'))

    class cacheinfo(nla):
        fields = (('ndm_confirmed', 'I'),
                  ('ndm_used', 'I'),
                  ('ndm_updated', 'I'),
                  ('ndm_refcnt', 'I'))
