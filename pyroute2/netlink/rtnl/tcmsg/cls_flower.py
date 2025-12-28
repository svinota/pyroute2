import socket

from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.common_act import get_tca_action, tca_act_prio
from pyroute2.netlink.rtnl.tcmsg.utils import *

# Default masks
DEFAULT_IPV4_MASK = '255.255.255.255'
DEFAULT_IPV6_MASK = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'


class FlowerArgs(object):
    SRC_MAC = 'src_mac'
    SRC_MAC_MASK = 'src_mac_mask'
    DST_MAC = 'dst_mac'
    DST_MAC_MASK = 'dst_mac_mask'
    ETH_TYPE = 'eth_type'

    SRC_IP = 'src_ip'
    SRC_MASK_IP = 'src_mask_ip'
    DST_IP = 'dst_ip'
    DST_MASK_IP = 'dst_mask_ip'
    IP_PROTO = 'ip_proto'
    VLAN_ID = 'vlan_id'

    SRC_PORT = 'src_port'
    DST_PORT = 'dst_port'

    IP_FLAGS = 'ip_flags'

    # Encapsulation (tunnel) parameters
    ENC_KEY_ID = 'enc_key_id'
    ENC_SRC_IP = 'enc_src_ip'
    ENC_SRC_IP_MASK = 'enc_src_ip_mask'
    ENC_DST_IP = 'enc_dst_ip'
    ENC_DST_IP_MASK = 'enc_dst_ip_mask'
    ENC_SRC_PORT = 'enc_src_port'
    ENC_DST_PORT = 'enc_dst_port'
    GENEVE_OPTS = 'geneve_opts'

    ACTION = 'action'


User2Nla = {
    FlowerArgs.SRC_MAC: 'TCA_FLOWER_KEY_ETH_SRC',
    FlowerArgs.DST_MAC: 'TCA_FLOWER_KEY_ETH_DST',
    FlowerArgs.SRC_MAC_MASK: 'TCA_FLOWER_KEY_ETH_SRC_MASK',
    FlowerArgs.DST_MAC_MASK: 'TCA_FLOWER_KEY_ETH_DST_MASK',
    FlowerArgs.ETH_TYPE: 'TCA_FLOWER_KEY_ETH_TYPE',
    FlowerArgs.ENC_KEY_ID: 'TCA_FLOWER_KEY_ENC_KEY_ID',
    FlowerArgs.ENC_SRC_PORT: 'TCA_FLOWER_KEY_ENC_UDP_SRC_PORT',
    FlowerArgs.ENC_DST_PORT: 'TCA_FLOWER_KEY_ENC_UDP_DST_PORT',
    FlowerArgs.IP_PROTO: 'TCA_FLOWER_KEY_IP_PROTO',
    FlowerArgs.IP_FLAGS: 'TCA_FLOWER_KEY_FLAGS',
    FlowerArgs.GENEVE_OPTS: 'TCA_FLOWER_KEY_ENC_OPTS',
    FlowerArgs.ACTION: 'TCA_FLOWER_ACT',
}

# Protocol-specific port mappings
Proto2PortNla = {
    socket.IPPROTO_TCP: {
        FlowerArgs.SRC_PORT: 'TCA_FLOWER_KEY_TCP_SRC',
        FlowerArgs.DST_PORT: 'TCA_FLOWER_KEY_TCP_DST',
    },
    socket.IPPROTO_UDP: {
        FlowerArgs.SRC_PORT: 'TCA_FLOWER_KEY_UDP_SRC',
        FlowerArgs.DST_PORT: 'TCA_FLOWER_KEY_UDP_DST',
    }
}

# IP version-specific mappings
IpVersion2Nla = {
    'ipv4': {
        FlowerArgs.SRC_IP: 'TCA_FLOWER_KEY_IPV4_SRC',
        FlowerArgs.SRC_MASK_IP: 'TCA_FLOWER_KEY_IPV4_SRC_MASK',
        FlowerArgs.DST_IP: 'TCA_FLOWER_KEY_IPV4_DST',
        FlowerArgs.DST_MASK_IP: 'TCA_FLOWER_KEY_IPV4_DST_MASK',
    },
    'ipv6': {
        FlowerArgs.SRC_IP: 'TCA_FLOWER_KEY_IPV6_SRC',
        FlowerArgs.SRC_MASK_IP: 'TCA_FLOWER_KEY_IPV6_SRC_MASK',
        FlowerArgs.DST_IP: 'TCA_FLOWER_KEY_IPV6_DST',
        FlowerArgs.DST_MASK_IP: 'TCA_FLOWER_KEY_IPV6_DST_MASK',
    }
}

# Encapsulation IP version-specific mappings
EncIpVersion2Nla = {
    'ipv4': {
        FlowerArgs.ENC_SRC_IP: 'TCA_FLOWER_KEY_ENC_IPV4_SRC',
        FlowerArgs.ENC_SRC_IP_MASK: 'TCA_FLOWER_KEY_ENC_IPV4_SRC_MASK',
        FlowerArgs.ENC_DST_IP: 'TCA_FLOWER_KEY_ENC_IPV4_DST',
        FlowerArgs.ENC_DST_IP_MASK: 'TCA_FLOWER_KEY_ENC_IPV4_DST_MASK',
    },
    'ipv6': {
        FlowerArgs.ENC_SRC_IP: 'TCA_FLOWER_KEY_ENC_IPV6_SRC',
        FlowerArgs.ENC_SRC_IP_MASK: 'TCA_FLOWER_KEY_ENC_IPV6_SRC_MASK',
        FlowerArgs.ENC_DST_IP: 'TCA_FLOWER_KEY_ENC_IPV6_DST',
        FlowerArgs.ENC_DST_IP_MASK: 'TCA_FLOWER_KEY_ENC_IPV6_DST_MASK',
    }
}


def fix_msg(msg, kwarg):
    if 'protocol' not in kwarg:
        protocol = detect_protocol(kwarg)
    else:
        protocol = kwarg['protocol']

    prio = kwarg.get('prio', 0)

    msg['info'] = build_tc_info_field(protocol, prio)


def get_parameters(kwarg):
    attrs = []
    ip_proto_val = None

    if FlowerArgs.IP_PROTO in kwarg:
        ip_proto_val = get_protocol_by_name(kwarg[FlowerArgs.IP_PROTO])
        if ip_proto_val is not None:
            attrs.append([User2Nla[FlowerArgs.IP_PROTO], ip_proto_val])

    if FlowerArgs.SRC_PORT in kwarg or FlowerArgs.DST_PORT in kwarg:
        if ip_proto_val is None:
            raise ValueError("src_port/dst_port requires ip_proto value (tcp, udp)")

        if ip_proto_val not in Proto2PortNla:
            raise ValueError(
                "Unsupported protocol for ports: {}".format(ip_proto_val))

        port_map = Proto2PortNla[ip_proto_val]

        if FlowerArgs.SRC_PORT in kwarg:
            attrs.append([port_map[FlowerArgs.SRC_PORT], kwarg[FlowerArgs.SRC_PORT]])

        if FlowerArgs.DST_PORT in kwarg:
            attrs.append([port_map[FlowerArgs.DST_PORT], kwarg[FlowerArgs.DST_PORT]])

    attrs.extend(_build_ip_attrs(
        kwarg, FlowerArgs.SRC_IP, FlowerArgs.SRC_MASK_IP, IpVersion2Nla))

    attrs.extend(_build_ip_attrs(
        kwarg, FlowerArgs.DST_IP, FlowerArgs.DST_MASK_IP, IpVersion2Nla))

    if FlowerArgs.IP_FLAGS in kwarg:
        ip_flags_val = kwarg[FlowerArgs.IP_FLAGS]
        if ip_flags_val == 'frag':
            attrs.append(['TCA_FLOWER_KEY_FLAGS', 1])
            attrs.append(['TCA_FLOWER_KEY_FLAGS_MASK', 1])
        elif ip_flags_val == 'nofrag':
            attrs.append(['TCA_FLOWER_KEY_FLAGS', 0])
            attrs.append(['TCA_FLOWER_KEY_FLAGS_MASK', 1])
        else:
            raise ValueError("ip_flags must be 'frag' or 'nofrag'")

    if FlowerArgs.SRC_MAC in kwarg:
        attrs.append([User2Nla[FlowerArgs.SRC_MAC], parse_mac(kwarg[FlowerArgs.SRC_MAC])])

        if FlowerArgs.SRC_MAC_MASK in kwarg:
            attrs.append([User2Nla[FlowerArgs.SRC_MAC_MASK], parse_mac(
                kwarg[FlowerArgs.SRC_MAC_MASK])])

    if FlowerArgs.DST_MAC in kwarg:
        attrs.append([User2Nla[FlowerArgs.DST_MAC],
                      parse_mac(kwarg[FlowerArgs.DST_MAC])])

        if FlowerArgs.DST_MAC_MASK in kwarg:
            attrs.append([User2Nla[FlowerArgs.DST_MAC_MASK],
                          parse_mac(kwarg[FlowerArgs.DST_MAC_MASK])])

    if FlowerArgs.ETH_TYPE in kwarg:
        eth_type = kwarg[FlowerArgs.ETH_TYPE]
    else:
        eth_type = _detect_eth_type(attrs)
    attrs.append([User2Nla[FlowerArgs.ETH_TYPE], eth_type])

    # Handle encapsulation (tunnel)
    if FlowerArgs.ENC_KEY_ID in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_KEY_ID], kwarg[FlowerArgs.ENC_KEY_ID]])

    attrs.extend(_build_ip_attrs(
        kwarg, FlowerArgs.ENC_SRC_IP, FlowerArgs.ENC_SRC_IP_MASK,
        EncIpVersion2Nla))

    attrs.extend(_build_ip_attrs(
        kwarg, FlowerArgs.ENC_DST_IP, FlowerArgs.ENC_DST_IP_MASK,
        EncIpVersion2Nla))

    if FlowerArgs.ENC_SRC_PORT in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_SRC_PORT],
                      kwarg[FlowerArgs.ENC_SRC_PORT]])

    if FlowerArgs.ENC_DST_PORT in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_DST_PORT], kwarg[FlowerArgs.ENC_DST_PORT]])

    if FlowerArgs.GENEVE_OPTS in kwarg:
        opts_str = kwarg[FlowerArgs.GENEVE_OPTS]
        opts_nested = _parse_geneve_opts(opts_str)
        mask_nested = _build_geneve_opts_mask(opts_str)
        attrs.append([User2Nla[FlowerArgs.GENEVE_OPTS], opts_nested])
        attrs.append(['TCA_FLOWER_KEY_ENC_OPTS_MASK', mask_nested])

    if FlowerArgs.ACTION in kwarg:
        attrs.append([User2Nla[FlowerArgs.ACTION], get_tca_action(kwarg)])

    return {'attrs': attrs}


def _build_ip_attrs(kwarg, ip_key, mask_key, nla_map):
    if ip_key not in kwarg:
        return []
    addr, mask = parse_ip(kwarg[ip_key])

    ip_ver = 'ipv6' if is_ipv6_addr(addr) else 'ipv4'
    nla_ip_map = nla_map[ip_ver]

    attrs = [[nla_ip_map[ip_key], addr]]

    if mask:
        attrs.append([nla_ip_map[mask_key], mask])
    else:
        default = DEFAULT_IPV6_MASK if ip_ver == 'ipv6' else DEFAULT_IPV4_MASK
        attrs.append([nla_ip_map[mask_key], default])

    return attrs


def _detect_eth_type(attrs):
    ipv4_nlas = set(IpVersion2Nla['ipv4'].values())
    ipv6_nlas = set(IpVersion2Nla['ipv6'].values())
    attr_keys = {attr[0] for attr in attrs}

    if attr_keys & ipv4_nlas:
        return protocols.ETH_P_IP
    if attr_keys & ipv6_nlas:
        return protocols.ETH_P_IPV6
    return protocols.ETH_P_ALL


def _parse_geneve_opts(opts_str):
    parts = opts_str.split(':')
    if len(parts) != 3:
        raise ValueError(
            "geneve_opts must be in format CLASS:TYPE:DATA (e.g., '0102:80:aabbccdd')"
        )

    opt_class = int(parts[0], 16)
    opt_type = int(parts[1], 16)
    opt_data = bytes.fromhex(parts[2])

    return {
        'attrs': [
            ['TCA_FLOWER_KEY_ENC_OPTS_GENEVE', {
                'attrs': [
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_CLASS', opt_class],
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_TYPE', opt_type],
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_DATA', opt_data],
                ]
            }]
        ]
    }


def _build_geneve_opts_mask(opts_str):
    parts = opts_str.split(':')
    if len(parts) != 3:
        raise ValueError("geneve_opts must be in format CLASS:TYPE:DATA")

    data_len = len(parts[2]) // 2  # hex string -> bytes length

    return {
        'attrs': [
            ['TCA_FLOWER_KEY_ENC_OPTS_GENEVE', {
                'attrs': [
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_CLASS', 0xFFFF],
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_TYPE', 0xFF],
                    ['TCA_FLOWER_KEY_ENC_OPT_GENEVE_DATA', bytes([0xFF] * data_len)],
                ]
            }]
        ]
    }


# Generated from /usr/include/linux/pkt_cls.h
class options(nla):
    nla_map = (
        ('TCA_FLOWER_UNSPEC', 'none'),
        ('TCA_FLOWER_CLASSID', 'uint32'),
        ('TCA_FLOWER_INDEV', 'asciiz'),
        ('TCA_FLOWER_ACT', 'tca_act_prio'),
        ('TCA_FLOWER_KEY_ETH_DST', 'l2addr'),
        ('TCA_FLOWER_KEY_ETH_DST_MASK', 'l2addr'),
        ('TCA_FLOWER_KEY_ETH_SRC', 'l2addr'),
        ('TCA_FLOWER_KEY_ETH_SRC_MASK', 'l2addr'),
        ('TCA_FLOWER_KEY_ETH_TYPE', 'be16'),
        ('TCA_FLOWER_KEY_IP_PROTO', 'uint8'),
        ('TCA_FLOWER_KEY_IPV4_SRC', 'ip4addr'),
        ('TCA_FLOWER_KEY_IPV4_SRC_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_IPV4_DST', 'ip4addr'),
        ('TCA_FLOWER_KEY_IPV4_DST_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_IPV6_SRC', 'ip6addr'),
        ('TCA_FLOWER_KEY_IPV6_SRC_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_IPV6_DST', 'ip6addr'),
        ('TCA_FLOWER_KEY_IPV6_DST_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_TCP_SRC', 'be16'),
        ('TCA_FLOWER_KEY_TCP_DST', 'be16'),
        ('TCA_FLOWER_KEY_UDP_SRC', 'be16'),
        ('TCA_FLOWER_KEY_UDP_DST', 'be16'),
        ('TCA_FLOWER_FLAGS', 'uint32'),
        ('TCA_FLOWER_KEY_VLAN_ID', 'uint16'),
        ('TCA_FLOWER_KEY_VLAN_PRIO', 'uint8'),
        ('TCA_FLOWER_KEY_VLAN_ETH_TYPE', 'be16'),
        ('TCA_FLOWER_KEY_ENC_KEY_ID', 'be32'),
        ('TCA_FLOWER_KEY_ENC_IPV4_SRC', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_SRC_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_DST', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_DST_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_SRC', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_SRC_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_DST', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_DST_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_TCP_SRC_MASK', 'be16'),
        ('TCA_FLOWER_KEY_TCP_DST_MASK', 'be16'),
        ('TCA_FLOWER_KEY_UDP_SRC_MASK', 'be16'),
        ('TCA_FLOWER_KEY_UDP_DST_MASK', 'be16'),
        ('TCA_FLOWER_KEY_SCTP_SRC_MASK', 'be16'),
        ('TCA_FLOWER_KEY_SCTP_DST_MASK', 'be16'),
        ('TCA_FLOWER_KEY_SCTP_SRC', 'be16'),
        ('TCA_FLOWER_KEY_SCTP_DST', 'be16'),
        ('TCA_FLOWER_KEY_ENC_UDP_SRC_PORT', 'be16'),
        ('TCA_FLOWER_KEY_ENC_UDP_SRC_PORT_MASK', 'be16'),
        ('TCA_FLOWER_KEY_ENC_UDP_DST_PORT', 'be16'),
        ('TCA_FLOWER_KEY_ENC_UDP_DST_PORT_MASK', 'be16'),
        ('TCA_FLOWER_KEY_FLAGS', 'be32'),
        ('TCA_FLOWER_KEY_FLAGS_MASK', 'be32'),
        ('TCA_FLOWER_KEY_ICMPV4_CODE', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV4_CODE_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV4_TYPE', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV4_TYPE_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV6_CODE', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV6_CODE_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV6_TYPE', 'uint8'),
        ('TCA_FLOWER_KEY_ICMPV6_TYPE_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ARP_SIP', 'ip4addr'),
        ('TCA_FLOWER_KEY_ARP_SIP_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ARP_TIP', 'ip4addr'),
        ('TCA_FLOWER_KEY_ARP_TIP_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ARP_OP', 'uint8'),
        ('TCA_FLOWER_KEY_ARP_OP_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ARP_SHA', 'l2addr'),
        ('TCA_FLOWER_KEY_ARP_SHA_MASK', 'l2addr'),
        ('TCA_FLOWER_KEY_ARP_THA', 'l2addr'),
        ('TCA_FLOWER_KEY_ARP_THA_MASK', 'l2addr'),
        ('TCA_FLOWER_KEY_MPLS_TTL', 'uint8'),
        ('TCA_FLOWER_KEY_MPLS_BOS', 'uint8'),
        ('TCA_FLOWER_KEY_MPLS_TC', 'uint8'),
        ('TCA_FLOWER_KEY_MPLS_LABEL', 'be32'),
        ('TCA_FLOWER_KEY_TCP_FLAGS', 'be16'),
        ('TCA_FLOWER_KEY_TCP_FLAGS_MASK', 'be16'),
        ('TCA_FLOWER_KEY_IP_TOS', 'uint8'),
        ('TCA_FLOWER_KEY_IP_TOS_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_IP_TTL', 'uint8'),
        ('TCA_FLOWER_KEY_IP_TTL_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_CVLAN_ID', 'be16'),
        ('TCA_FLOWER_KEY_CVLAN_PRIO', 'uint8'),
        ('TCA_FLOWER_KEY_CVLAN_ETH_TYPE', 'be16'),
        ('TCA_FLOWER_KEY_ENC_IP_TOS', 'uint8'),
        ('TCA_FLOWER_KEY_ENC_IP_TOS_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ENC_IP_TTL', 'uint8'),
        ('TCA_FLOWER_KEY_ENC_IP_TTL_MASK', 'uint8'),
        ('TCA_FLOWER_KEY_ENC_OPTS', 'tca_flower_key_enc_opts'),
        ('TCA_FLOWER_KEY_ENC_OPTS_MASK', 'tca_flower_key_enc_opts'),
        ('TCA_FLOWER_IN_HW_COUNT', 'hex'),
        ('TCA_FLOWER_KEY_PORT_SRC_MIN', 'be16'),
        ('TCA_FLOWER_KEY_PORT_SRC_MAX', 'be16'),
        ('TCA_FLOWER_KEY_PORT_DST_MIN', 'be16'),
        ('TCA_FLOWER_KEY_PORT_DST_MAX', 'be16'),
        ('TCA_FLOWER_KEY_CT_STATE', 'uint16'),
        ('TCA_FLOWER_KEY_CT_STATE_MASK', 'uint16'),
        ('TCA_FLOWER_KEY_CT_ZONE', 'uint16'),
        ('TCA_FLOWER_KEY_CT_ZONE_MASK', 'uint16'),
        ('TCA_FLOWER_KEY_CT_MARK', 'uint32'),
        ('TCA_FLOWER_KEY_CT_MARK_MASK', 'uint32'),
        ('TCA_FLOWER_KEY_CT_LABELS', 'hex'),
        ('TCA_FLOWER_KEY_CT_LABELS_MASK', 'hex'),
        ('TCA_FLOWER_KEY_MPLS_OPTS', 'hex'),
        ('TCA_FLOWER_KEY_HASH', 'uint32'),
        ('TCA_FLOWER_KEY_HASH_MASK', 'uint32'),
    )

    tca_act_prio = tca_act_prio

    class tca_flower_key_enc_opts(nla):
        nla_map = (
            ('TCA_FLOWER_KEY_ENC_OPTS_UNSPEC', 'none'),
            ('TCA_FLOWER_KEY_ENC_OPTS_GENEVE', 'tca_flower_key_enc_opt_geneve'),
        )

        class tca_flower_key_enc_opt_geneve(nla):
            nla_map = (
                ('TCA_FLOWER_KEY_ENC_OPT_GENEVE_UNSPEC', 'none'),
                ('TCA_FLOWER_KEY_ENC_OPT_GENEVE_CLASS', 'be16'),
                ('TCA_FLOWER_KEY_ENC_OPT_GENEVE_TYPE', 'uint8'),
                ('TCA_FLOWER_KEY_ENC_OPT_GENEVE_DATA', 'hex'),
            )
