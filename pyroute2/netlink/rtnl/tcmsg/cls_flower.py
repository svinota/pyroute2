import socket

from pyroute2 import protocols
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.tcmsg.utils import build_tc_info_field, \
    detect_protocol, parse_mac, parse_ip, is_ipv6_addr, get_protocol_by_name
from pyroute2.netlink.rtnl.tcmsg.common_act import get_tca_action

# Default masks
DEFAULT_IPV4_MASK = '255.255.255.255'
DEFAULT_IPV6_MASK = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'

class FlowerArgs(object):
    SRC_MAC   = 'src_mac'
    SRC_MAC_MASK = 'src_mac_mask'
    DST_MAC   = 'dst_mac'
    DST_MAC_MASK = 'dst_mac_mask'
    ETH_TYPE = 'eth_type'

    SRC_IP    = 'src_ip'
    DST_IP    = 'dst_ip'
    IP_PROTO  = 'ip_proto'
    VLAN_ID   = 'vlan_id'

    SRC_PORT  = 'src_port'
    DST_PORT  = 'dst_port'

    IP_FLAGS  = 'ip_flags'

    # Encapsulation (tunnel) parameters
    ENC_KEY_ID = 'enc_key_id'
    ENC_SRC_IP = 'enc_src_ip'
    ENC_DST_IP = 'enc_dst_ip'
    ENC_SRC_PORT = 'enc_src_port'
    ENC_DST_PORT = 'enc_dst_port'
    GENEVE_OPTS = 'geneve_opts'

    ACTION = 'action'


User2Nla = {
    FlowerArgs.SRC_MAC:         'TCA_FLOWER_KEY_ETH_SRC',
    FlowerArgs.DST_MAC:         'TCA_FLOWER_KEY_ETH_DST',
    FlowerArgs.SRC_MAC_MASK:    'TCA_FLOWER_KEY_ETH_SRC_MASK',
    FlowerArgs.DST_MAC_MASK:    'TCA_FLOWER_KEY_ETH_DST_MASK',
    FlowerArgs.ETH_TYPE:        'TCA_FLOWER_KEY_ETH_TYPE',
    FlowerArgs.ENC_KEY_ID:      'TCA_FLOWER_KEY_ENC_KEY_ID',
    FlowerArgs.ENC_SRC_PORT:    'TCA_FLOWER_KEY_ENC_UDP_SRC_PORT',
    FlowerArgs.ENC_DST_PORT:    'TCA_FLOWER_KEY_ENC_UDP_DST_PORT',
    FlowerArgs.IP_PROTO:        'TCA_FLOWER_KEY_IP_PROTO',
    FlowerArgs.IP_FLAGS:        'TCA_FLOWER_KEY_FLAGS',
    FlowerArgs.GENEVE_OPTS:     'TCA_FLOWER_KEY_ENC_OPTS',
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
        'src': 'TCA_FLOWER_KEY_IPV4_SRC',
        'src_mask': 'TCA_FLOWER_KEY_IPV4_SRC_MASK',
        'dst': 'TCA_FLOWER_KEY_IPV4_DST',
        'dst_mask': 'TCA_FLOWER_KEY_IPV4_DST_MASK',
    },
    'ipv6': {
        'src': 'TCA_FLOWER_KEY_IPV6_SRC',
        'src_mask': 'TCA_FLOWER_KEY_IPV6_SRC_MASK',
        'dst': 'TCA_FLOWER_KEY_IPV6_DST',
        'dst_mask': 'TCA_FLOWER_KEY_IPV6_DST_MASK',
    }
}

# Encapsulation IP version-specific mappings
EncIpVersion2Nla = {
    'ipv4': {
        'src': 'TCA_FLOWER_KEY_ENC_IPV4_SRC',
        'src_mask': 'TCA_FLOWER_KEY_ENC_IPV4_SRC_MASK',
        'dst': 'TCA_FLOWER_KEY_ENC_IPV4_DST',
        'dst_mask': 'TCA_FLOWER_KEY_ENC_IPV4_DST_MASK',
    },
    'ipv6': {
        'src': 'TCA_FLOWER_KEY_ENC_IPV6_SRC',
        'src_mask': 'TCA_FLOWER_KEY_ENC_IPV6_SRC_MASK',
        'dst': 'TCA_FLOWER_KEY_ENC_IPV6_DST',
        'dst_mask': 'TCA_FLOWER_KEY_ENC_IPV6_DST_MASK',
    }
}


def fix_request(msg, kwarg):
    if 'protocol' not in kwarg:
        kwarg['protocol'] = detect_protocol(msg['parent'])
    else:
        msg['protocol'] = kwarg['protocol']

    msg['info'] = build_tc_info_field(msg, kwarg)

def parse_geneve_opts(opts_str):
    return bytes.fromhex(opts_str.replace(':', ''))


def get_parameters(kwarg):
    attrs = []

    has_ipv4_attrs = False
    has_ipv6_attrs = False
    ip_proto_val = None

    if FlowerArgs.IP_PROTO in kwarg:
        ip_proto_val = get_protocol_by_name(kwarg[FlowerArgs.IP_PROTO])
        if ip_proto_val is not None:
            attrs.append([User2Nla[FlowerArgs.IP_PROTO], ip_proto_val])

    if FlowerArgs.SRC_PORT in kwarg or FlowerArgs.DST_PORT in kwarg:
        if ip_proto_val is None:
            raise ValueError("src_port/dst_port requires ip_proto value (tcp, udp)")

        if ip_proto_val not in Proto2PortNla:
            raise ValueError("Unsupported protocol for ports: ".format(
                ip_proto_val))

        port_map = Proto2PortNla[ip_proto_val]

        if FlowerArgs.SRC_PORT in kwarg:
            attrs.append([port_map[FlowerArgs.SRC_PORT], kwarg[FlowerArgs.SRC_PORT]])

        if FlowerArgs.DST_PORT in kwarg:
            attrs.append([port_map[FlowerArgs.DST_PORT], kwarg[FlowerArgs.DST_PORT]])

    if FlowerArgs.SRC_IP in kwarg:
        addr, mask = parse_ip(kwarg[FlowerArgs.SRC_IP])

        ip_version = 'ipv6' if is_ipv6_addr(addr) else 'ipv4'
        ip_map = IpVersion2Nla[ip_version]
        default_mask = DEFAULT_IPV6_MASK if ip_version == 'ipv6' else DEFAULT_IPV4_MASK

        if ip_version == 'ipv6':
            has_ipv6_attrs = True
        else:
            has_ipv4_attrs = True

        attrs.append([ip_map['src'], addr])
        attrs.append([ip_map['src_mask'], mask or default_mask])

    if FlowerArgs.DST_IP in kwarg:
        addr, mask = parse_ip(kwarg[FlowerArgs.DST_IP])
        ip_version = 'ipv6' if is_ipv6_addr(addr) else 'ipv4'
        ip_map = IpVersion2Nla[ip_version]
        default_mask = DEFAULT_IPV6_MASK if ip_version == 'ipv6' else DEFAULT_IPV4_MASK

        if ip_version == 'ipv6':
            has_ipv6_attrs = True
        else:
            has_ipv4_attrs = True

        attrs.append([ip_map['dst'], addr])
        attrs.append([ip_map['dst_mask'], mask or default_mask])

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
        attrs.append([User2Nla[FlowerArgs.ETH_TYPE], kwarg[FlowerArgs.ETH_TYPE]])
    else:
        if has_ipv4_attrs:
            attrs.append([User2Nla[FlowerArgs.ETH_TYPE], protocols.ETH_P_IP])
        elif has_ipv6_attrs:
            attrs.append([User2Nla[FlowerArgs.ETH_TYPE], protocols.ETH_P_IPV6])
        else:
            attrs.append([User2Nla[FlowerArgs.ETH_TYPE], protocols.ETH_P_ALL])

    # Handle encapsulation (tunnel)
    if FlowerArgs.ENC_KEY_ID in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_KEY_ID], kwarg[FlowerArgs.ENC_KEY_ID]])

    if FlowerArgs.ENC_SRC_IP in kwarg:
        addr, mask = parse_ip(kwarg[FlowerArgs.ENC_SRC_IP])
        ip_version = 'ipv6' if is_ipv6_addr(addr) else 'ipv4'
        enc_ip_map = EncIpVersion2Nla[ip_version]

        attrs.append([enc_ip_map['src'], addr])
        if mask:
            attrs.append([enc_ip_map['src_mask'], mask])

    if FlowerArgs.ENC_DST_IP in kwarg:
        addr, mask = parse_ip(kwarg[FlowerArgs.ENC_DST_IP])
        ip_version = 'ipv6' if is_ipv6_addr(addr) else 'ipv4'
        enc_ip_map = EncIpVersion2Nla[ip_version]

        attrs.append([enc_ip_map['dst'], addr])
        if mask:
            attrs.append([enc_ip_map['dst_mask'], mask])

    if FlowerArgs.ENC_SRC_PORT in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_SRC_PORT],
                     kwarg[FlowerArgs.ENC_SRC_PORT]])

    if FlowerArgs.ENC_DST_PORT in kwarg:
        attrs.append([User2Nla[FlowerArgs.ENC_DST_PORT], kwarg[FlowerArgs.ENC_DST_PORT]])

    if FlowerArgs.GENEVE_OPTS in kwarg:
        opts_bytes = parse_geneve_opts(kwarg[FlowerArgs.GENEVE_OPTS])
        attrs.append([User2Nla[FlowerArgs.GENEVE_OPTS], opts_bytes])
        attrs.append(['TCA_FLOWER_KEY_ENC_OPTS_MASK', bytes([0xff] * len(opts_bytes))])

    if FlowerArgs.ACTION in kwarg:
        attrs.append([User2Nla[FlowerArgs.ACTION], get_tca_action(kwarg)])

    return {'attrs': attrs}



class options(nla):
    nla_map = (
        ('TCA_FLOWER_UNSPEC', 'none'),
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
        ('TCA_FLOWER_KEY_ENC_KEY_ID', 'be32'),
        ('TCA_FLOWER_KEY_ENC_IPV4_SRC', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_SRC_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_DST', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV4_DST_MASK', 'ip4addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_SRC', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_SRC_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_DST', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_IPV6_DST_MASK', 'ip6addr'),
        ('TCA_FLOWER_KEY_ENC_UDP_SRC_PORT', 'be16'),
        ('TCA_FLOWER_KEY_ENC_UDP_DST_PORT', 'be16'),
        ('TCA_FLOWER_KEY_ENC_OPTS', 'hex'),
        ('TCA_FLOWER_KEY_ENC_OPTS_MASK', 'hex'),
        ('TCA_FLOWER_KEY_FLAGS', 'be32'),
        ('TCA_FLOWER_KEY_FLAGS_MASK', 'be32'),
    )
