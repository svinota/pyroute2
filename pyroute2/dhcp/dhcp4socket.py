from pyroute2.protocols import udpmsg
from pyroute2.protocols import udp4_pseudo_header
from pyroute2.protocols import ethmsg
from pyroute2.protocols import ip4msg
from pyroute2.protocols.rawsocket import RawSocket
from pyroute2.dhcp.dhcp4msg import dhcp4msg


def listen_udp_port(port=68):
    bpf_code = [[40, 0, 0, 12],
                [21, 0, 8, 2048],
                [48, 0, 0, 23],
                [21, 0, 6, 17],
                [40, 0, 0, 20],
                [69, 4, 0, 8191],
                [177, 0, 0, 14],
                [72, 0, 0, 16],
                [21, 0, 1, port],
                [6, 0, 0, 65535],
                [6, 0, 0, 0]]
    return bpf_code


class DHCP4Socket(RawSocket):

    def __init__(self, ifname):
        RawSocket.__init__(self, ifname, listen_udp_port(68))

    def put(self, options=None, msg=None, addr='255.255.255.255', port=67):
        # DHCP layer
        options = options or {}
        dhcp = msg or dhcp4msg({'op': 1,
                                'htype': 1,
                                'hlen': 6,
                                'chaddr': self.l2addr,
                                'options': options})

        # fill required fields
        if dhcp['op'] is None:
            dhcp['op'] = 1  # request
        if dhcp['htype'] is None:
            dhcp['htype'] = 1  # ethernet
        if (dhcp['hlen'] is None) and (dhcp['htype'] == 1):
            dhcp['hlen'] = 6  # ethernet MAC
            dhcp['chaddr'] = self.l2addr
        if dhcp['xid'] is None:
            dhcp['xid'] = 15
        dhcp.mtype = 1
        data = dhcp.encode().buf

        # UDP layer
        udp = udpmsg({'sport': 68,
                      'dport': 67,
                      'len': 8 + len(data)})
        udph = udp4_pseudo_header({'dst': '255.255.255.255',
                                   'len': 8 + len(data)})
        udp['csum'] = self.csum(udph.encode().buf + udp.encode().buf + data)
        udp.reset()

        # IPv4 layer
        ip4 = ip4msg({'len': 20 + 8 + len(data),
                      'proto': 17,
                      'dst': '255.255.255.255'})
        ip4['csum'] = self.csum(ip4.encode().buf)
        ip4.reset()

        # MAC layer
        eth = ethmsg({'dst': 'ff:ff:ff:ff:ff:ff',
                      'src': self.l2addr,
                      'type': 0x800})

        data = eth.encode().buf +\
            ip4.encode().buf +\
            udp.encode().buf +\
            data
        self.send(data)

    def get(self):
        (data, addr) = self.recvfrom(4096)
        eth = ethmsg(buf=data).decode()
        ip4 = ip4msg(buf=data, offset=eth.offset).decode()
        udp = udpmsg(buf=data, offset=ip4.offset).decode()
        return dhcp4msg(buf=data, offset=udp.offset).decode()
