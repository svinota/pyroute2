import socket

from pyroute2 import protocols


def parse_mac(mac_str):
    return bytes.fromhex(mac_str.replace(':', ''))


def parse_ip(ip_str):
    addr, _, prefix = ip_str.partition('/')

    if not prefix:
        return addr, None

    prefix = int(prefix)
    if is_ipv6_addr(addr):
        bits = 128
        family = socket.AF_INET6
    else:
        bits = 32
        family = socket.AF_INET

    mask = (1 << bits) - (1 << (bits - prefix))
    mask_bytes = mask.to_bytes(bits // 8, 'big')
    mask_str = socket.inet_ntop(family, mask_bytes)

    return addr, mask_str


def detect_protocol(kwargs):
    for ip_field in ['src_ip', 'dst_ip']:
        if ip_field in kwargs:
            if is_ipv6_addr(ip_field):
                return protocols.ETH_P_IPV6

            return protocols.ETH_P_IP

    return protocols.ETH_P_ALL


def build_tc_info_field(protocol, prio):
    return socket.htons(protocol & 0xFFFF) | ((prio << 16) & 0xFFFF0000)


def is_ipv6_addr(addr):
    return ':' in addr

def get_protocol_by_name(protocol_name):
    try:
        return socket.getprotobyname(protocol_name)
    except OSError:
        return None
