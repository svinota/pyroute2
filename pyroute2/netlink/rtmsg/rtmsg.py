
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla


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

    fields = ("family",
              "dst_len",
              "src_len",
              "tos",
              "table",
              "proto",
              "scope",
              "type",
              "flags")

    nla_map = (('RTA_UNSPEC', 'none'),
               ('RTA_DST', 'ipaddr'),
               ('RTA_SRC', 'ipaddr'),
               ('RTA_IIF', 'uint32'),
               ('RTA_OIF', 'uint32'),
               ('RTA_GATEWAY', 'ipaddr'),
               ('RTA_PRIORITY', 'uint32'),
               ('RTA_PREFSRC', 'ipaddr'),
               ('RTA_METRICS', 'uint32'),
               ('RTA_MULTIPATH', 'hex'),
               ('RTA_PROTOINFO', 'hex'),
               ('RTA_FLOW', 'hex'),
               ('RTA_CACHEINFO', 'cacheinfo'),
               ('RTA_SESSION', 'hex'),
               ('RTA_MP_ALGO', 'hex'),
               ('RTA_TABLE', 'uint32'))

    class cacheinfo(nla):
        fmt = "IIiIIIII"
        fields = ('rta_clntref',
                  'rta_lastuse',
                  'rta_expires',
                  'rta_error',
                  'rta_used',
                  'rta_id',
                  'rta_ts',
                  'rta_tsage')
