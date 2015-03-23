import struct
from socket import socket
from socket import inet_ntop
from socket import inet_pton
from socket import AF_INET
from socket import SOCK_DGRAM
from socket import SOL_SOCKET
from socket import SO_BROADCAST
from socket import SO_REUSEADDR
from socket import SO_BINDTODEVICE


class dhcpmsg(dict):
    buf = None
    fields = ()
    _fields_names = ()
    types = {'uint8': 'B',
             'uint16': 'H',
             'uint32': 'I',
             'ip4addr': ['4s',
                         lambda x: inet_ntop(AF_INET, x),
                         lambda x: inet_pton(AF_INET, x)]}

    def __init__(self, buf=b''):
        self.buf = buf

    def _register_fields(self):
        self._fields_names = tuple([x[0] for x in self.fields])

    def _get_routine(self, mode, fmt):
        fmt = self.types.get(fmt, fmt)
        if isinstance(fmt, (list, set, tuple)):
            return (fmt[0], fmt[1] if mode == 'decode' else fmt[2])
        else:
            return (fmt, lambda x: x)

    def decode(self):
        offset = 0
        self._register_fields()
        for name, fmt in self.fields:
            fmt, routine = self._get_routine('decode', fmt)
            size = struct.calcsize(fmt)
            value = struct.unpack(fmt, self.buf[offset:offset + size])[0]
            self[name] = routine(value)
            offset += size

    def encode(self):
        self.buf = b''
        self._register_fields()
        for name, fmt in self.fields:
            fmt, routine = self._get_routine('encode', fmt)
            size = struct.calcsize(fmt)
            if self[name] is None:
                self.buf += b'\x00' * size
            else:
                self.buf += struct.pack(fmt, routine(self[name]))

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if key in self._fields_names:
                return None
            raise


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
              ('chaddr', '16s'),
              ('sname', '64s'),
              ('file', '128s'))


class DHCP4Socket(socket):

    def __init__(self, ifname):
        self.ifname = ifname

        socket.__init__(self, AF_INET, SOCK_DGRAM)
        socket.setsockopt(self, SOL_SOCKET, SO_BROADCAST, 1)
        socket.setsockopt(self, SOL_SOCKET, SO_REUSEADDR, 1)
        socket.setsockopt(self, SOL_SOCKET, SO_BINDTODEVICE, self.ifname)
        socket.bind(self, ('', 68))
