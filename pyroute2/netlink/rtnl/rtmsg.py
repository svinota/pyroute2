
from pyroute2.netlink.generic import nlmsg
from pyroute2.netlink.generic import nla


class rtmsg(nlmsg):
    '''
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
    '''
    prefix = 'RTA_'

    fields = (('family', 'B'),
              ('dst_len', 'B'),
              ('src_len', 'B'),
              ('tos', 'B'),
              ('table', 'B'),
              ('proto', 'B'),
              ('scope', 'B'),
              ('type', 'B'),
              ('flags', 'I'))

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
               ('RTA_PROTOINFO', 'uint32'),
               ('RTA_FLOW', 'hex'),
               ('RTA_CACHEINFO', 'cacheinfo'),
               ('RTA_SESSION', 'hex'),
               ('RTA_MP_ALGO', 'hex'),
               ('RTA_TABLE', 'uint32'))

    class cacheinfo(nla):
        fields = (('rta_clntref', 'I'),
                  ('rta_lastuse', 'I'),
                  ('rta_expires', 'i'),
                  ('rta_error', 'I'),
                  ('rta_used', 'I'),
                  ('rta_id', 'I'),
                  ('rta_ts', 'I'),
                  ('rta_tsage', 'I'))
