import struct
from socket import inet_ntop
from socket import inet_pton
from socket import AF_UNSPEC
from socket import AF_INET
from socket import AF_INET6
from pyroute2.common import AF_MPLS
from pyroute2.common import hexdump
from pyroute2.netlink import nlmsg
from pyroute2.netlink import nla


class rtmsg_base(object):
    '''
    Route message

    C structure::

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
               ('RTA_DST', 'target'),
               ('RTA_SRC', 'target'),
               ('RTA_IIF', 'uint32'),
               ('RTA_OIF', 'uint32'),
               ('RTA_GATEWAY', 'target'),
               ('RTA_PRIORITY', 'uint32'),
               ('RTA_PREFSRC', 'target'),
               ('RTA_METRICS', 'metrics'),
               ('RTA_MULTIPATH', '*get_nh'),
               ('RTA_PROTOINFO', 'uint32'),
               ('RTA_FLOW', 'uint32'),
               ('RTA_CACHEINFO', 'cacheinfo'),
               ('RTA_SESSION', 'hex'),
               ('RTA_MP_ALGO', 'hex'),
               ('RTA_TABLE', 'uint32'),
               ('RTA_MARK', 'uint32'),
               ('RTA_MFC_STATS', 'rta_mfc_stats'),
               ('RTA_VIA', 'rtvia'),
               ('RTA_NEWDST', 'target'),
               ('RTA_PREF', 'hex'),
               ('RTA_ENCAP_TYPE', 'uint16'),
               ('RTA_ENCAP', 'encap_info'),
               ('RTA_EXPIRES', 'hex'))

    @staticmethod
    def encap_info(self, *argv, **kwarg):
        return self.mpls_encap_info

    class mpls_encap_info(nla):
        nla_map = (('MPLS_IPTUNNEL_UNSPEC', 'none'),
                   ('MPLS_IPTUNNEL_DST', 'mpls_target'))

    class rta_mfc_stats(nla):
        fields = (('mfcs_packets', 'uint64'),
                  ('mfcs_bytes', 'uint64'),
                  ('mfcs_wrong_if', 'uint64'))

    class metrics(nla):
        prefix = 'RTAX_'
        nla_map = (('RTAX_UNSPEC', 'none'),
                   ('RTAX_LOCK', 'uint32'),
                   ('RTAX_MTU', 'uint32'),
                   ('RTAX_WINDOW', 'uint32'),
                   ('RTAX_RTT', 'uint32'),
                   ('RTAX_RTTVAR', 'uint32'),
                   ('RTAX_SSTHRESH', 'uint32'),
                   ('RTAX_CWND', 'uint32'),
                   ('RTAX_ADVMSS', 'uint32'),
                   ('RTAX_REORDERING', 'uint32'),
                   ('RTAX_HOPLIMIT', 'uint32'),
                   ('RTAX_INITCWND', 'uint32'),
                   ('RTAX_FEATURES', 'uint32'),
                   ('RTAX_RTO_MIN', 'uint32'),
                   ('RTAX_INITRWND', 'uint32'),
                   ('RTAX_QUICKACK', 'uint32'))

    @staticmethod
    def get_nh(self, *argv, **kwarg):
        return nh

    class rtvia(nla):
        fields = (('value', 's'), )

        def encode(self):
            family = self.get('family', AF_UNSPEC)
            if family in (AF_INET, AF_INET6):
                addr = inet_pton(family, self['addr'])
            else:
                raise TypeError('Family %s not supported for RTA_VIA'
                                % family)
            self['value'] = struct.pack('H', family) + addr
            nla.encode(self)

        def decode(self):
            nla.decode(self)
            family = struct.unpack('H', self['value'][:2])[0]
            addr = self['value'][2:]
            if len(addr):
                if (family == AF_INET and len(addr) == 4) or \
                        (family == AF_INET6 and len(addr) == 16):
                    addr = inet_ntop(family, addr)
                else:
                    addr = hexdump(addr)
            self.value = {'family': family, 'addr': addr}

    class cacheinfo(nla):
        fields = (('rta_clntref', 'I'),
                  ('rta_lastuse', 'I'),
                  ('rta_expires', 'i'),
                  ('rta_error', 'I'),
                  ('rta_used', 'I'),
                  ('rta_id', 'I'),
                  ('rta_ts', 'I'),
                  ('rta_tsage', 'I'))


class rtmsg(rtmsg_base, nlmsg):

    def encode(self):
        if self.get('family') == AF_MPLS:
            # force fields
            self['dst_len'] = 20
            self['table'] = 254
            self['type'] = 1
            # assert NLA types
            for n in self.get('attrs', []):
                if n[0] not in ('RTA_OIF',
                                'RTA_DST',
                                'RTA_VIA',
                                'RTA_NEWDST',
                                'RTA_MULTIPATH'):
                    raise TypeError('Incorrect NLA type %s for AF_MPLS' % n[0])
        nlmsg.encode(self)


class nh(rtmsg_base, nla):
    is_nla = False
    cell_header = (('length', 'H'), )
    fields = (('flags', 'B'),
              ('hops', 'B'),
              ('oif', 'i'))
