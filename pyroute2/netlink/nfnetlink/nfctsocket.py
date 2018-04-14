"""
NFCTSocket -- low level connection tracking API

See also: pyroute2.conntrack
"""

import socket

from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NETLINK_NETFILTER
from pyroute2.netlink import nla
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.nfnetlink import nfgen_msg
from pyroute2.netlink.nfnetlink import NFNL_SUBSYS_CTNETLINK

IPCTNL_MSG_CT_NEW = 0
IPCTNL_MSG_CT_GET = 1
IPCTNL_MSG_CT_DELETE = 2
IPCTNL_MSG_CT_GET_CTRZERO = 3
IPCTNL_MSG_CT_GET_STATS_CPU = 4
IPCTNL_MSG_CT_GET_STATS = 5
IPCTNL_MSG_CT_GET_DYING = 6
IPCTNL_MSG_CT_GET_UNCONFIRMED = 7
IPCTNL_MSG_MAX = 8

# Window scaling is advertised by the sender
IP_CT_TCP_FLAG_WINDOW_SCALE = 0x01

# SACK is permitted by the sender
IP_CT_TCP_FLAG_SACK_PERM = 0x02

# This sender sent FIN first
IP_CT_TCP_FLAG_CLOSE_INIT = 0x04

# Be liberal in window checking
IP_CT_TCP_FLAG_BE_LIBERAL = 0x08

# Has unacknowledged data
IP_CT_TCP_FLAG_DATA_UNACKNOWLEDGED = 0x10

# The field td_maxack has been set
IP_CT_TCP_FLAG_MAXACK_SET = 0x20


def terminate_single_msg(msg):
    return msg


class nfct_stats(nfgen_msg):
    nla_map = (
        ('CTA_STATS_GLOBAL_UNSPEC', 'none'),
        ('CTA_STATS_GLOBAL_ENTRIES', 'be32'),
    )


class nfct_stats_cpu(nfgen_msg):
    nla_map = (
        ('CTA_STATS_UNSPEC', 'none'),
        ('CTA_STATS_SEARCHED', 'be32'),
        ('CTA_STATS_FOUND', 'be32'),
        ('CTA_STATS_NEW', 'be32'),
        ('CTA_STATS_INVALID', 'be32'),
        ('CTA_STATS_IGNORE', 'be32'),
        ('CTA_STATS_DELETE', 'be32'),
        ('CTA_STATS_DELETE_LIST', 'be32'),
        ('CTA_STATS_INSERT', 'be32'),
        ('CTA_STATS_INSERT_FAILED', 'be32'),
        ('CTA_STATS_DROP', 'be32'),
        ('CTA_STATS_EARLY_DROP', 'be32'),
        ('CTA_STATS_ERROR', 'be32'),
        ('CTA_STATS_SEARCH_RESTART', 'be32'),
    )


class nfct_msg(nfgen_msg):
    nla_map = (
        ('CTA_UNSPEC', 'none'),
        ('CTA_TUPLE_ORIG', 'cta_tuple'),
        ('CTA_TUPLE_REPLY', 'cta_tuple'),
        ('CTA_STATUS', 'be32'),
        ('CTA_PROTOINFO', 'cta_protoinfo'),
        ('CTA_HELP', 'asciiz'),
        ('CTA_NAT_SRC', 'cta_nat'),
        ('CTA_TIMEOUT', 'be32'),
        ('CTA_MARK', 'be32'),
        ('CTA_COUNTERS_ORIG', 'cta_counters'),
        ('CTA_COUNTERS_REPLY', 'cta_counters'),
        ('CTA_USE', 'be32'),
        ('CTA_ID', 'be32'),
        ('CTA_NAT_DST', 'cta_nat'),
        ('CTA_TUPLE_MASTER', 'cta_tuple'),
        ('CTA_SEQ_ADJ_ORIG', 'cta_nat_seq_adj'),
        ('CTA_SEQ_ADJ_REPLY', 'cta_nat_seq_adj'),
        ('CTA_SECMARK', 'be32'),
        ('CTA_ZONE', 'be16'),
        ('CTA_SECCTX', 'cta_secctx'),
        ('CTA_TIMESTAMP', 'cta_timestamp'),
        ('CTA_MARK_MASK', 'be32'),
        ('CTA_LABELS', 'cta_labels'),
        ('CTA_LABELS_MASK', 'cta_labels'),
    )

    class cta_tuple(nla):
        nla_map = (
            ('CTA_TUPLE_UNSPEC', 'none'),
            ('CTA_TUPLE_IP', 'cta_ip'),
            ('CTA_TUPLE_PROTO', 'cta_proto'),
        )

        class cta_ip(nla):
            nla_map = (
                ('CTA_IP_UNSPEC', 'none'),
                ('CTA_IP_V4_SRC', 'ip4addr'),
                ('CTA_IP_V4_DST', 'ip4addr'),
                ('CTA_IP_V6_SRC', 'ip6addr'),
                ('CTA_IP_V6_DST', 'ip6addr'),
            )

        class cta_proto(nla):
            nla_map = (
                ('CTA_PROTO_UNSPEC', 'none'),
                ('CTA_PROTO_NUM', 'uint8'),
                ('CTA_PROTO_SRC_PORT', 'be16'),
                ('CTA_PROTO_DST_PORT', 'be16'),
                ('CTA_PROTO_ICMP_ID', 'be16'),
                ('CTA_PROTO_ICMP_TYPE', 'uint8'),
                ('CTA_PROTO_ICMP_CODE', 'uint8'),
                ('CTA_PROTO_ICMPV6_ID', 'be16'),
                ('CTA_PROTO_ICMPV6_TYPE', 'uint8'),
                ('CTA_PROTO_ICMPV6_CODE', 'uint8'),
            )

    class cta_protoinfo(nla):
        nla_map = (
            ('CTA_PROTOINFO_UNSPEC', 'none'),
            ('CTA_PROTOINFO_TCP', 'cta_protoinfo_tcp'),
            ('CTA_PROTOINFO_DCCP', 'cta_protoinfo_dccp'),
            ('CTA_PROTOINFO_SCTP', 'cta_protoinfo_sctp'),
        )

        class cta_protoinfo_tcp(nla):
            nla_map = (
                ('CTA_PROTOINFO_TCP_UNSPEC', 'none'),
                ('CTA_PROTOINFO_TCP_STATE', 'uint8'),
                ('CTA_PROTOINFO_TCP_WSCALE_ORIGINAL', 'uint8'),
                ('CTA_PROTOINFO_TCP_WSCALE_REPLY', 'uint8'),
                ('CTA_PROTOINFO_TCP_FLAGS_ORIGINAL', 'cta_tcp_flags'),
                ('CTA_PROTOINFO_TCP_FLAGS_REPLY', 'cta_tcp_flags'),
            )

            class cta_tcp_flags(nla):
                fields = [('value', 'BB')]

        class cta_protoinfo_dccp(nla):
            nla_map = (
                ('CTA_PROTOINFO_DCCP_UNSPEC', 'none'),
                ('CTA_PROTOINFO_DCCP_STATE', 'uint8'),
                ('CTA_PROTOINFO_DCCP_ROLE', 'uint8'),
                ('CTA_PROTOINFO_DCCP_HANDSHAKE_SEQ', 'be64'),
            )

        class cta_protoinfo_sctp(nla):
            nla_map = (
                ('CTA_PROTOINFO_SCTP_UNSPEC', 'none'),
                ('CTA_PROTOINFO_SCTP_STATE', 'uint8'),
                ('CTA_PROTOINFO_SCTP_VTAG_ORIGINAL', 'be32'),
                ('CTA_PROTOINFO_SCTP_VTAG_REPLY', 'be32'),
            )

    class cta_nat(nla):
        nla_map = (
            ('CTA_NAT_UNSPEC', 'none'),
            ('CTA_NAT_V4_MINIP', 'ip4addr'),
            ('CTA_NAT_V4_MAXIP', 'ip4addr'),
            ('CTA_NAT_PROTO', 'cta_protonat'),
            ('CTA_NAT_V6_MINIP', 'ip6addr'),
            ('CTA_NAT_V6_MAXIP', 'ip6addr'),
        )

        class cta_protonat(nla):
            nla_map = (
                ('CTA_PROTONAT_UNSPEC', 'none'),
                ('CTA_PROTONAT_PORT_MIN', 'be16'),
                ('CTA_PROTONAT_PORT_MAX', 'be16'),
            )

    class cta_nat_seq_adj(nla):
        nla_map = (
            ('CTA_NAT_SEQ_UNSPEC', 'none'),
            ('CTA_NAT_SEQ_CORRECTION_POS', 'be32'),
            ('CTA_NAT_SEQ_OFFSET_BEFORE', 'be32'),
            ('CTA_NAT_SEQ_OFFSET_AFTER', 'be32'),
        )

    class cta_counters(nla):
        nla_map = (
            ('CTA_COUNTERS_UNSPEC', 'none'),
            ('CTA_COUNTERS_PACKETS', 'be64'),
            ('CTA_COUNTERS_BYTES', 'be64'),
            ('CTA_COUNTERS32_PACKETS', 'be32'),
            ('CTA_COUNTERS32_BYTES', 'be32'),
        )

    class cta_secctx(nla):
        nla_map = (
            ('CTA_SECCTX_UNSPEC', 'none'),
            ('CTA_SECCTX_NAME', 'asciiz'),
        )

    class cta_timestamp(nla):
        nla_map = (
            ('CTA_TIMESTAMP_UNSPEC', 'none'),
            ('CTA_TIMESTAMP_START', 'be64'),
            ('CTA_TIMESTAMP_STOP', 'be64'),
        )

    class cta_labels(nla):
        fields = [('value', 'QQ')]

        def encode(self):
            if not isinstance(self['value'], tuple):
                self['value'] = (self['value'] & 0xffffffffffffffff,
                                 self['value'] >> 64)
            nla.encode(self)

        def decode(self):
            nla.decode(self)
            if isinstance(self['value'], tuple):
                self['value'] = (self['value'][0] & 0xffffffffffffffff) | \
                                (self['value'][1] << 64)


class NFCTSocket(NetlinkSocket):
    policy = dict((k | (NFNL_SUBSYS_CTNETLINK << 8), v) for k, v in {
        IPCTNL_MSG_CT_NEW: nfct_msg,
        IPCTNL_MSG_CT_GET: nfct_msg,
        IPCTNL_MSG_CT_DELETE: nfct_msg,
        IPCTNL_MSG_CT_GET_CTRZERO: nfct_msg,
        IPCTNL_MSG_CT_GET_STATS_CPU: nfct_stats_cpu,
        IPCTNL_MSG_CT_GET_STATS: nfct_stats,
        IPCTNL_MSG_CT_GET_DYING: nfct_msg,
        IPCTNL_MSG_CT_GET_UNCONFIRMED: nfct_msg,
    }.items())

    def __init__(self, nfgen_family=socket.AF_INET):
        super(NFCTSocket, self).__init__(family=NETLINK_NETFILTER)
        self.register_policy(self.policy)
        self._nfgen_family = nfgen_family

    def request(self, msg, msg_type, **kwargs):
        msg['nfgen_family'] = self._nfgen_family
        msg_type |= (NFNL_SUBSYS_CTNETLINK << 8)
        return self.nlm_request(msg, msg_type, **kwargs)

    def dump(self, mark=None, mark_mask=0xffffffff):
        msg = self._mkmsg(mark=mark, mark_mask=mark_mask)
        return self.request(msg, IPCTNL_MSG_CT_GET,
                            msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def stat(self):
        return self.request(nfct_msg(), IPCTNL_MSG_CT_GET_STATS_CPU,
                            msg_flags=NLM_F_REQUEST | NLM_F_DUMP)

    def count(self):
        return self.request(nfct_msg(), IPCTNL_MSG_CT_GET_STATS,
                            msg_flags=NLM_F_REQUEST | NLM_F_DUMP,
                            terminate=terminate_single_msg)

    def flush(self, mark=None, mark_mask=0xffffffff, zone=None):
        msg = self._mkmsg(mark=mark, mark_mask=mark_mask, zone=zone)
        return self.request(msg, IPCTNL_MSG_CT_DELETE,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK)

    def delete(self, saddr, daddr, proto, sport=None, dport=None,
               icmp_id=None, icmp_type=None, icmp_code=None,
               id=None, mark=None, mark_mask=0xffffffff, zone=None,
               direction='orig'):
        if direction not in ['orig', 'reply']:
            raise ValueError('Invalid direction: %s' % direction)

        msg = self._mkmsg(
            tuple_type=direction,
            saddr=saddr, daddr=daddr, proto=proto,
            sport=sport, dport=dport,
            icmp_id=icmp_id, icmp_type=icmp_type, icmp_code=icmp_code,
            id=id, mark=mark, mark_mask=mark_mask, zone=zone)
        return self.request(msg, IPCTNL_MSG_CT_DELETE,
                            msg_flags=NLM_F_REQUEST | NLM_F_ACK)

    def _mkmsg(self, **kwargs):
        def haskey(key):
            return kwargs.get(key) is not None

        msg = nfct_msg()

        if haskey('id'):
            msg['attrs'] += [['CTA_ID', kwargs['id']]]

        if haskey('zone'):
            msg['attrs'] += [['CTA_ZONE', kwargs['zone']]]

        if haskey('mark'):
            mark = kwargs['mark']
            mark_mask = kwargs.get('mark_mask', 0xffffffff)
            msg['attrs'] += [['CTA_MARK', mark]]
            msg['attrs'] += [['CTA_MARK_MASK', mark_mask]]

        if haskey('tuple_type'):
            cta_ip = []
            cta_proto = []
            cta_tuple = []

            if self._nfgen_family == socket.AF_INET:
                ipkey = 'CTA_IP_V4'
                icmpkey = 'CTA_PROTO_ICMP'
            elif self._nfgen_family == socket.AF_INET6:
                ipkey = 'CTA_IP_V6'
                icmpkey = 'CTA_PROTO_ICMPV6'
            else:
                raise ValueError('Unknown family: %s' % self._nfgen_family)

            if haskey('saddr'):
                cta_ip += [[ipkey + '_SRC', kwargs['saddr']]]

            if haskey('daddr'):
                cta_ip += [[ipkey + '_DST', kwargs['daddr']]]

            if haskey('proto'):
                cta_proto += [['CTA_PROTO_NUM', kwargs['proto']]]

            if haskey('sport'):
                cta_proto += [['CTA_PROTO_SRC_PORT', kwargs['sport']]]

            if haskey('dport'):
                cta_proto += [['CTA_PROTO_DST_PORT', kwargs['dport']]]

            if haskey('icmp_id'):
                cta_proto += [[icmpkey + '_ID', kwargs['icmp_id']]]

            if haskey('icmp_type'):
                cta_proto += [[icmpkey + '_TYPE', kwargs['icmp_type']]]

            if haskey('icmp_code'):
                cta_proto += [[icmpkey + '_CODE', kwargs['icmp_code']]]

            if cta_ip:
                cta_tuple += [['CTA_TUPLE_IP', {'attrs': cta_ip}]]

            if cta_proto:
                cta_tuple += [['CTA_TUPLE_PROTO', {'attrs': cta_proto}]]

            if cta_tuple:
                tuple_type = 'CTA_TUPLE_' + kwargs['tuple_type'].upper()
                msg['attrs'] += [[tuple_type, {'attrs': cta_tuple}]]

        return msg
