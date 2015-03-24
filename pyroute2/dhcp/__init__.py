import struct
from socket import socket
from socket import htons
from socket import inet_ntop
from socket import inet_pton
from socket import AF_INET
from socket import AF_PACKET
from socket import SOCK_RAW
from socket import SOCK_DGRAM
from socket import SOL_SOCKET
from socket import SO_BROADCAST
from socket import SO_REUSEADDR
from socket import SO_BINDTODEVICE
from pyroute2 import IPRoute

ETH_P_ALL = 3


class msg(dict):
    buf = None
    fields = ()
    _fields_names = ()
    types = {'uint8': 'B',
             'uint16': 'H',
             'uint32': 'I',
             'be16': '>H',
             'dhcp_cookie': {'format': '>I',
                             'default': struct.pack('>I', 0x63825363)},
             'ip4addr': {'format': '4s',
                         'decode': lambda x: inet_ntop(AF_INET, x),
                         'encode': lambda x: [inet_pton(AF_INET, x)]},
             'l2addr': {'format': '6B',
                        'decode': lambda x: ':'.join(x),
                        'encode': lambda x: [int(i, 16) for i in
                                             x.split(':')]},
             'l2paddr': {'format': '6B10s',
                         'decode': lambda x: ':'.join(x[:-1]),
                         'encode': lambda x: [int(i, 16) for i in
                                              x.split(':')] + [10 * '\x00']}}

    def __init__(self, content=None, buf=b''):
        content = content or {}
        dict.__init__(self, content)
        self.buf = buf
        self._register_fields()

    def _register_fields(self):
        self._fields_names = tuple([x[0] for x in self.fields])

    def _get_routine(self, mode, fmt):
        fmt = self.types.get(fmt, fmt)
        if isinstance(fmt, dict):
            return (fmt['format'],
                    fmt.get(mode, lambda x: [x]),
                    fmt.get('default', b'\x00'))
        else:
            return (fmt, lambda x: [x], b'\x00')

    def decode(self):
        offset = 0
        self._register_fields()
        for name, fmt in self.fields:
            fmt, routine, default = self._get_routine('decode', fmt)
            size = struct.calcsize(fmt)
            value = struct.unpack(fmt, self.buf[offset:offset + size])[0]
            self[name] = routine(value)
            offset += size
        return self

    def encode(self):
        self.buf = b''
        self._register_fields()
        for name, fmt in self.fields:
            fmt, routine, default = self._get_routine('encode', fmt)
            size = struct.calcsize(fmt)
            if self[name] is None:
                self.buf += default * size
            else:
                self.buf += struct.pack(fmt, *routine(self[name]))
        return self

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if key in self._fields_names:
                return None
            raise


class ethmsg(msg):
    fields = (('dst', 'l2addr'),
              ('src', 'l2addr'),
              ('type', 'be16'))


class ip4msg(msg):
    fields = (('verlen', 'uint8'),
              ('dsf', 'uint8'),
              ('len', 'be16'),
              ('id', 'be16'),
              ('flags', 'uint16'),
              ('ttl', 'uint8'),
              ('proto', 'uint8'),
              ('csum', 'be16'),
              ('src', 'ip4addr'),
              ('dst', 'ip4addr'))


class udp4_pseudo_header(msg):
    fields = (('src', 'ip4addr'),
              ('dst', 'ip4addr'),
              ('pad', 'uint8'),
              ('proto', 'uint8'),
              ('len', 'be16'))


class udpmsg(msg):
    fields = (('sport', 'be16'),
              ('dport', 'be16'),
              ('len', 'be16'),
              ('csum', 'be16'))


class dhcp4msg(msg):
    #
    # https://www.ietf.org/rfc/rfc2131.txt
    #
    fields = (('op', 'uint8'),
              ('htype', 'uint8'),
              ('hlen', 'uint8'),
              ('hops', 'uint8'),
              ('xid', 'uint32'),
              ('secs', 'uint16'),
              ('flags', 'uint16'),
              ('ciaddr', 'ip4addr'),
              ('yiaddr', 'ip4addr'),
              ('siaddr', 'ip4addr'),
              ('giaddr', 'ip4addr'),
              ('chaddr', 'l2paddr'),
              ('sname', '64s'),
              ('file', '128s'),
              ('cookie', 'dhcp_cookie'))


class DHCP4Socket(socket):

    def __init__(self, ifname):
        self.ifname = ifname
        # lookup the interface details
        ip = IPRoute()
        for link in ip.get_links():
            if link.get_attr('IFLA_IFNAME') == ifname:
                break
        else:
            raise IOError(2, 'Link not found')
        self.l2addr = link.get_attr('IFLA_ADDRESS')
        self.ifindex = link['index']
        # bring up the socket
        socket.__init__(self, AF_INET, SOCK_DGRAM)
        socket.setsockopt(self, SOL_SOCKET, SO_BROADCAST, 1)
        socket.setsockopt(self, SOL_SOCKET, SO_REUSEADDR, 1)
        socket.setsockopt(self, SOL_SOCKET, SO_BINDTODEVICE, self.ifname)
        socket.bind(self, ('', 68))

        # create raw send socket
        self.raw = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))
        self.raw.bind((ifname, ETH_P_ALL))

    def csum(self, data):
        if len(data) % 2:
            data += '\x00'
        csum = sum([struct.unpack('>H', data[x*2:x*2+2])[0] for x
                    in range(len(data)/2)])
        csum = (csum >> 16) + (csum & 0xffff)
        csum += csum >> 16
        return ~csum & 0xffff

    def send_raw(self, data):
        eth = ethmsg({'dst': 'ff:ff:ff:ff:ff:ff',
                      'src': self.l2addr,
                      'type': 0x800})
        ip4 = ip4msg({'verlen': 0x45,
                      'len': 20 + 8 + len(data),
                      'ttl': 128,
                      'proto': 17,
                      'dst': '255.255.255.255'})
        ip4['csum'] = self.csum(ip4.encode().buf)
        udp = udpmsg({'sport': 68,
                      'dport': 67,
                      'len': 8 + len(data)})
        udph = udp4_pseudo_header({'dst': '255.255.255.255',
                                   'proto': 17,
                                   'len': 8 + len(data)})
        udp['csum'] = self.csum(udph.encode().buf + udp.encode().buf + data)
        data = eth.encode().buf +\
            ip4.encode().buf +\
            udp.encode().buf +\
            data
        self.raw.send(data)

    def put(self, msg=None, addr='255.255.255.255', port=67):
        msg = msg or dhcp4msg({'op': 1,
                               'htype': 1,
                               'hlen': 6,
                               'chaddr': self.l2addr})

        # fill required fields
        if msg['op'] is None:
            msg['op'] = 1  # request
        if msg['htype'] is None:
            msg['htype'] = 1  # ethernet
        if (msg['hlen'] is None) and (msg['htype'] == 1):
            msg['hlen'] = 6  # ethernet MAC
            msg['chaddr'] = self.l2addr
        if msg['xid'] is None:
            msg['xid'] = 15
        msg.encode()
        self.send_raw(msg.buf)

    def get(self):
        (data, addr) = self.recvfrom(4096)
        return dhcp4msg(buf=data).decode()
