import array
import struct
from pyroute2.common import basestring
from pyroute2.protocols import msg


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

    def decode(self):
        if self.policy is not None:
            length = struct.unpack('B', self.buf[self.offset + 1:
                                                 self.offset + 2])[0]
            if self.policy['fmt'] == 'string':
                fmt = '%is' % length
            else:
                fmt = self.policy['fmt']
            value = struct.unpack(fmt, self.buf[self.offset + 2:
                                                self.offset + 2 + length])
            if len(value) == 1:
                value = value[0]
            value = self.policy.get('decode', lambda x: x)(value)
            if isinstance(value, basestring) and \
                    self.policy['fmt'] == 'string':
                value = value[:value.find('\x00')]
            self.value = value
        else:
            msg.decode(self)
        return self


class dhcpmsg(msg):
    options = ()
    l2addr = None
    _encode_map = {}
    _decode_map = {}

    def _register_options(self):
        for option in self.options:
            code, name, fmt = option[:3]
            self._decode_map[code] =\
                self._encode_map[name] = {'name': name,
                                          'code': code,
                                          'fmt': fmt}

    def decode(self):
        msg.decode(self)
        self._register_options()
        self['options'] = {}
        while self.offset < len(self.buf):
            code = struct.unpack('B', self.buf[self.offset:self.offset + 1])[0]
            if code == 0:
                self.offset += 1
                continue
            if code == 255:
                return self
            # code is unknown -- bypass it
            if code not in self._decode_map:
                length = struct.unpack('B', self.buf[self.offset + 1:
                                                     self.offset + 2])[0]
                self.offset += length + 2
                continue

            # code is known, work on it
            option_class = getattr(self, self._decode_map[code]['fmt'])
            option = option_class(buf=self.buf, offset=self.offset)
            option.decode()
            self.offset += option.length
            if option.value is not None:
                value = option.value
            else:
                value = option
            self['options'][self._decode_map[code]['name']] = value
        return self

    def encode(self):
        msg.encode(self)
        self._register_options()
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

    class client_id(option):
        fields = (('type', 'uint8'),
                  ('key', 'l2addr'))
