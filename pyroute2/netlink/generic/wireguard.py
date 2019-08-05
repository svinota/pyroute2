from base64 import b64encode
from binascii import a2b_hex
from socket import inet_ntoa, AF_INET
from struct import pack
from time import ctime

from pyroute2.netlink import genlmsg
from pyroute2.netlink import nla
from pyroute2.netlink import nla_base
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.nlsocket import Marshal


# Defines from uapi/wireguard.h
WG_GENL_NAME = "wireguard"
WG_KEY_LEN = 32

# WireGuard Device commands
WG_CMD_GET_DEVICE = 0
WG_CMD_SET_DEVICE = 1

# Wireguard Device attributes
WG_DEVICE_A_UNSPEC = 0
WG_DEVICE_A_IFINDEX = 1
WG_DEVICE_A_IFNAME = 2
WG_DEVICE_A_PRIVATE_KEY = 3
WG_DEVICE_A_PUBLIC_KEY = 4
WG_DEVICE_A_FLAGS = 5
WG_DEVICE_A_LISTEN_PORT = 6
WG_DEVICE_A_FWMARK = 7
WG_DEVICE_A_PEERS = 8

# WireGuard Allowed IP attributes
WGALLOWEDIP_A_UNSPEC = 0
WGALLOWEDIP_A_FAMILY = 1
WGALLOWEDIP_A_IPADDR = 2
WGALLOWEDIP_A_CIDR_MASK = 3

# Netlink internal family ID for WireGuard (0x18)
WG_FAMILY_ID = 24


class wgmsg(genlmsg):
    prefix = 'WGDEVICE_A_'

    nla_map = (('WGDEVICE_A_UNSPEC', 'none'),
               ('WGDEVICE_A_IFINDEX', 'uint32'),
               ('WGDEVICE_A_IFNAME', 'asciiz'),
               ('WGDEVICE_A_PRIVATE_KEY', 'parse_wg_key'),
               ('WGDEVICE_A_PUBLIC_KEY', 'parse_wg_key'),
               ('WGDEVICE_A_FLAGS', 'uint32'),
               ('WGDEVICE_A_LISTEN_PORT', 'uint16'),
               ('WGDEVICE_A_FWMARK', 'uint32'),
               ('WGDEVICE_A_PEERS', 'wgdevice_a_peers'))

    class wgdevice_a_peers(nla):
        nla_map = tuple([('WGDEVICE_A_PEER_%i' % x, 'wgdevice_peer') for x
                         in range(1000)])

        class wgdevice_peer(nla):
            prefix = 'WGPEER_A_'

            nla_map = (('WGPEER_A_UNSPEC', 'none'),
                       ('WGPEER_A_PUBLIC_KEY', 'parse_peer_key'),
                       ('WGPEER_A_PRESHARED_KEY', 'parse_peer_key'),
                       ('WGPEER_A_FLAGS', 'uint32'),
                       ('WGPEER_A_ENDPOINT', 'parse_endpoint'),
                       ('WGPEER_A_PERSISTENT_KEEPALIVE_INTERVAL', 'uint16'),
                       ('WGPEER_A_LAST_HANDSHAKE_TIME', 'parse_handshake_time'),
                       ('WGPEER_A_RX_BYTES', 'uint64'),
                       ('WGPEER_A_TX_BYTES', 'uint64'),
                       ('WGPEER_A_ALLOWEDIPS', 'wgpeer_a_allowedips'),
                       ('WGPEER_A_PROTOCOL_VERSION', 'uint32'))

            class parse_peer_key(nla):

                def decode(self):
                    nla.decode(self)
                    self['key'] = b64encode(bytearray(self.data[self.offset:self.offset + WG_KEY_LEN]))

            class parse_endpoint(nla):
                fields = (('family', 'H'),
                          ('port', '>H'),
                          ('addr4', '>I'),
                          ('addr6', 's'))

                def decode(self):
                    nla.decode(self)
                    if self['family'] == AF_INET:
                        self['addr'] = inet_ntoa(pack('>I', self['addr4']))
                    else:
                        self['addr'] = self['addr6']
                    del self['addr4']
                    del self['addr6']

            class parse_handshake_time(nla):
                fields = (('tv_sec', 'Q'),
                          ('tv_nsec', 'Q'))

                def decode(self):
                    nla.decode(self)
                    self['latest handshake'] = ctime(self['tv_sec'])

            class wgpeer_a_allowedips(nla):
                nla_map = tuple([('WGPEER_A_ALLOWEDIPS_%i' % x, 'wgpeer_allowedip') for x
                                 in range(1000)])

                class wgpeer_allowedip(nla):
                    prefix = 'WGALLOWEDIP_A_'

                    nla_map = (('WGALLOWEDIP_A_UNSPEC', 'none'),
                               ('WGALLOWEDIP_A_FAMILY', 'uint16'),
                               ('WGALLOWEDIP_A_IPADDR', 'hex'),
                               ('WGALLOWEDIP_A_CIDR_MASK', 'uint8'))

                    def decode(self):
                        nla.decode(self)
                        if self.get_attr('WGALLOWEDIP_A_FAMILY') == AF_INET:
                            self['addr'] = inet_ntoa(a2b_hex(self.get_attr('WGALLOWEDIP_A_IPADDR').replace(':', '')))
                        else:
                            self['addr'] = self.get_attr('WGALLOWEDIP_A_IPADDR')
                        self['addr'] = '{0}/{1}'.format(self['addr'], self.get_attr('WGALLOWEDIP_A_CIDR_MASK'))

    class parse_wg_key(nla):

        def decode(self):
            nla.decode(self)
            self['value'] = b64encode(self['value'])


class MarshalWireGuard(Marshal):
    msg_map = {WG_FAMILY_ID: wgmsg}


class WireGuard(GenericNetlinkSocket):

    def __init__(self):
        GenericNetlinkSocket.__init__(self)
        self.marshal = MarshalWireGuard()

    def bind(self, groups=0, **kwarg):
        GenericNetlinkSocket.bind(self, WG_GENL_NAME, wgmsg,
                                  groups, None, **kwarg)