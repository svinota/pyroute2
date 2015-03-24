import array
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
from pyroute2.common import basestring

ETH_P_ALL = 3


class msg(dict):
    buf = None
    fields = ()
    _fields_names = ()
    types = {'uint8': 'B',
             'uint16': 'H',
             'uint32': 'I',
             'be16': '>H',
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

    def __init__(self, content=None, buf=b'', offset=0, value=None):
        content = content or {}
        dict.__init__(self, content)
        self.buf = buf
        self.offset = 0
        self.value = value
        self._register_fields()

    def _register_fields(self):
        self._fields_names = tuple([x[0] for x in self.fields])

    def _get_routine(self, mode, fmt):
        fmt = self.types.get(fmt, fmt)
        if isinstance(fmt, dict):
            return (fmt['format'],
                    fmt.get(mode, lambda x: [x]))
        else:
            return (fmt, lambda x: [x])

    def reset(self):
        self.buf = b''

    def decode(self):
        self._register_fields()
        for field in self.fields:
            name, fmt = field[:2]
            fmt, routine = self._get_routine('decode', fmt)
            size = struct.calcsize(fmt)
            value = struct.unpack(fmt, self.buf[self.offset:
                                                self.offset + size])[0]
            self[name] = routine(value)
            self.offset += size
        return self

    def encode(self):
        self._register_fields()
        for field in self.fields:
            name, fmt = field[:2]
            default = '\x00' if len(field) <= 2 else field[2]
            fmt, routine = self._get_routine('encode', fmt)
            # special case: string
            if fmt == 'string':
                self.buf += routine(self[name])[0]
            else:
                size = struct.calcsize(fmt)
                if self[name] is None:
                    if not isinstance(default, basestring):
                        self.buf += struct.pack(fmt, default)
                    else:
                        self.buf += default * (size / len(default))
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


class option(msg):

    code = 0
    policy = None
    value = None

    def __init__(self, content=None, buf=b'', offset=0, value=None, code=0):
        msg.__init__(self, content=content, buf=buf,
                     offset=offset, value=value)
        self.code = code

    @property
    def length(self):
        data_length = self.data_length
        if data_length == 0:
            return 1
        else:
            return data_length + 2

    @property
    def data_length(self):
        s = 0
        for field in self.fields:
            fmt, routine = self._get_routine('decode', field[1])
            if fmt == 'string':
                s += len(self[field[0]])
            else:
                s += struct.calcsize(fmt)
        if s == 0 and self.policy is not None:
            if self.policy['fmt'] == 'string':
                s = len(self.value)
            else:
                s = struct.calcsize(self.policy['fmt'])
        return s

    def encode(self):
        # pack code
        self.buf += struct.pack('B', self.code)
        if self.code in (0, 255):
            return self
        self.buf += struct.pack('B', self.data_length)
        if self.policy is not None:
            value = self.policy.get('encode', lambda x: x)(self.value)
            if self.policy['fmt'] == 'string':
                fmt = '%is' % len(value)
            else:
                fmt = self.policy['fmt']
            self.buf += struct.pack(fmt, value)
        else:
            msg.encode(self)
        return self


class dhcpmsg(msg):
    options = ()
    l2addr = None

    def _register_options(self):
        for option in self.options:
            code, name, fmt = option[:3]
            self._decode_map[code] =\
                self._encode_map[name] = {'name': name,
                                          'code': code,
                                          'fmt': fmt}

    def decode(self):
        msg.decode(self)
        while self.offset < len(self.buf):
            code = struct.unpack('B', self.buf[self.offset:self.offset + 1])
            # code is unknown -- bypass it
            if code not in self._decode_map:
                length = struct.unpack('B', self.buf[self.offset + 1:
                                                     self.offset + 2])
                self.offset += length + 2
                continue

            # code is known, work on it
            option_class = getattr(self, self._decode_map[code]['fmt'])
            option = option_class(buf=self.buf, offset=self.offset + 2)
            option.decode()
            self.offset += option.length
            self['options'][self._decode_map[code]['name']] = option
        return self

    def encode(self):
        msg.encode(self)
        # put message type
        self.buf += self.uint8(code=53, value=self.mtype).encode().buf
        self.buf += self.client_id({'type': 1,
                                    'key': self['chaddr']},
                                   code=61).encode().buf
        self.buf += self.string(code=60, value='pyroute2').encode().buf

        for (name, value) in self.get('options', {}):
            fmt = self._encode_map.get(name, {'fmt': None})['fmt']
            if fmt is None:
                continue
            # name is known, ok
            option_class = getattr(self, fmt)
            if isinstance(value, dict):
                option = option_class(value,
                                      code=self._encode_map[name]['code'])
            else:
                option = option_class(code=self._encode_map[name]['code'],
                                      value=value)
            self.buf += option.encode().buf

        self.buf += self.none(code=255).encode().buf
        return self

    class none(option):
        pass

    class be16(option):
        policy = {'fmt': '>H'}

    class be32(option):
        policy = {'fmt': '>I'}

    class uint8(option):
        policy = {'fmt': 'B'}

    class string(option):
        policy = {'fmt': 'string'}

    class array8(option):
        policy = {'fmt': 'string',
                  'encode': lambda x: array.array('B', x).tostring(),
                  'decode': lambda x: array.array('B', x).tolist()}

    class ip4addr(option):
        policy = {'fmt': '4s',
                  'encode': lambda x: inet_pton(AF_INET, x),
                  'decode': lambda x: inet_ntop(AF_INET, x)}

    class client_id(option):
        fields = (('type', 'uint8'),
                  ('key', 'l2addr'))


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


class dhcp4msg(dhcpmsg):
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
              ('cookie', '4s', 'c\x82Sc'))
    #
    # https://www.ietf.org/rfc/rfc2132.txt
    #
    options = ((0, 'pad', 'none'),
               (1, 'subnet_mask', 'ip4addr'),
               (2, 'time_offset', 'be32'),
               (3, 'router', 'ip4addr'),
               (4, 'time_server', 'ip4addr'),
               (5, 'ien_name_server', 'ip4addr'),
               (6, 'name_server', 'ip4addr'),
               (7, 'log_server', 'ip4addr'),
               (8, 'cookie_server', 'ip4addr'),
               (9, 'lpr_server', 'ip4addr'),
               (53, 'message_type', 'uint8'),
               (55, 'parameter_list', 'array8'),
               (57, 'messagi_size', 'be16'),
               (60, 'vendor_id', 'string'),
               (61, 'client_id', 'client_id'),
               (255, 'end', 'none'))


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
        ip4.reset()
        udp = udpmsg({'sport': 68,
                      'dport': 67,
                      'len': 8 + len(data)})
        udph = udp4_pseudo_header({'dst': '255.255.255.255',
                                   'proto': 17,
                                   'len': 8 + len(data)})
        udp['csum'] = self.csum(udph.encode().buf + udp.encode().buf + data)
        udp.reset()
        data = eth.encode().buf +\
            ip4.encode().buf +\
            udp.encode().buf +\
            data
        self.raw.send(data)

    def put(self, options=None, msg=None, addr='255.255.255.255', port=67):
        options = options or {}
        msg = msg or dhcp4msg({'op': 1,
                               'htype': 1,
                               'hlen': 6,
                               'chaddr': self.l2addr,
                               'options': options})

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
        msg.mtype = 1
        msg.encode()
        self.send_raw(msg.buf)

    def get(self):
        (data, addr) = self.recvfrom(4096)
        return dhcp4msg(buf=data).decode()
