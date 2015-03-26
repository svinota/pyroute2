from pyroute2.common import AddrPool
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
        # Create xid pool
        #
        # Every allocated xid will be released automatically after 1024
        # alloc() calls, there is no need to call free(). Minimal xid == 16
        self.xid_pool = AddrPool(minaddr=16, release=1024)

    def put(self, msg=None, options=None, port=67):
        # DHCP layer
        dhcp = msg or dhcp4msg({'chaddr': self.l2addr,
                                'options': options})
        # dhcp transaction id
        if dhcp['xid'] is None:
            dhcp['xid'] = self.xid_pool.alloc()

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
        dhcp.reset()
        return dhcp

    def get(self):
        (data, addr) = self.recvfrom(4096)
        eth = ethmsg(buf=data).decode()
        ip4 = ip4msg(buf=data, offset=eth.offset).decode()
        udp = udpmsg(buf=data, offset=ip4.offset).decode()
        return dhcp4msg(buf=data, offset=udp.offset).decode()
