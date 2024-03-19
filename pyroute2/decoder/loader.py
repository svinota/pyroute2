import io
import json
import shlex
import struct
from collections import namedtuple
from importlib import import_module

from pyroute2.common import hexdump

PcapMetaData = namedtuple(
    "pCAPMetaData",
    (
        "magic_number",
        "version_major",
        "version_minor",
        "thiszone",
        "sigfigs",
        "snaplen",
        "network",
    ),
)
PcapPacketHeader = namedtuple(
    "PcapPacketHeader",
    ("ts_sec", "ts_usec", "incl_len", "orig_len", "header_len"),
)
PcapLLHeader = namedtuple(
    "PcapLLHeader",
    ("pad0", "addr_type", "pad1", "pad2", "pad3", "family", "header_len"),
)


class Message:

    def __init__(self, packet_header, ll_header, met, data):
        self.packet_header = packet_header
        self.ll_header = ll_header
        self.cls = None
        self.met = met
        self.data = data
        self.exception = None
        self.msg = None

    def get_message_class(self):
        if hasattr(self.met, 'msg_map'):
            (msg_type,) = struct.unpack('H', self.data[4:6])
            return self.met.msg_map[msg_type]
        return self.met

    def decode(self):
        try:
            self.cls = self.get_message_class()
            self.msg = self.cls(self.data)
            self.msg.decode()
            self.msg = self.msg.dump()
        except Exception as e:
            self.exception = repr(e)
            self.msg = hexdump(self.data)

    def __repr__(self):
        return json.dumps(
            {
                "pcap header": repr(self.packet_header),
                "link layer header": repr(self.ll_header),
                "message class": repr(self.cls),
                "exception": self.exception,
                "data": self.msg,
            },
            indent=4,
        )


class MatchOps:

    @staticmethod
    def AND():
        def f(packet_header, ll_header, raw, data_offset, stack):
            v1 = stack.pop()
            v2 = stack.pop()
            return v1 and v2

        return f

    @staticmethod
    def OR():
        def f(packet_header, ll_header, raw, data_offset, stack):
            v1 = stack.pop()
            v2 = stack.pop()
            return v1 or v2

        return f

    @staticmethod
    def ll_header(family):
        if not isinstance(family, int) or family < 0 or family > 0xffff:
            raise TypeError('family must be unsigned short integer')
        def f(packet_header, ll_header, raw, data_offset, stack):
            return ll_header.family == family

        return f

    @staticmethod
    def data(fmt, offset, value):
        if not isinstance(fmt, str):
            raise TypeError('format must be string')
        if not isinstance(offset, int) or not isinstance(value, int):
            raise TypeError('offset and value must be integers')
        def f(packet_header, ll_header, raw, data_offset, stack):
            o = data_offset + offset
            s = struct.calcsize(fmt)
            return struct.unpack(fmt, raw[o : o + s])[0] == value

        return f


class Matcher:
    def __init__(self, script):
        self.parsed = []
        self.filters = []
        self.script = script
        self.shlex = shlex.shlex(instream=io.StringIO(script))
        self.shlex.wordchars += '-~'
        postpone = None
        while True:
            token = self.get_token(ignore=',')
            if token == '':
                break
            method = getattr(MatchOps, token)
            if token in ('AND', 'OR'):
                postpone = method
                continue
            kwarg = {}
            token = self.get_token(expect='{')
            while True:
                token = self.get_token(ignore=',')
                if token in ('}', ''):
                    break
                self.get_token(expect='=')
                value = self.get_token()
                if value[0] in ['"', "'"]:
                    # string
                    value = value[1:-1]
                else:
                    # int
                    value = int(value)
                kwarg[token] = value
            self.filters.append(method(**kwarg))
            if postpone is not None:
                self.filters.append(postpone())
                postpone = None

    def get_token(self, expect=None, ignore=None):
        token = self.shlex.get_token()
        self.parsed.append(token)
        if expect is not None and token != expect:
            raise SyntaxError(f"expected {expect}: {' '.join(self.parsed)} <-")
        if ignore is not None and token in ignore:
            token = self.shlex.get_token()
            self.parsed.append(token)
        return token

    def match(self, packet_header, ll_header, data, offset):
        stack = []
        for method in self.filters:
            stack.append(method(packet_header, ll_header, data, offset, stack))
        return all(stack)


class LoaderPcap:

    def __init__(self, data, cls, script):
        with open(data, 'rb') as f:
            self.raw = f.read()
        self.metadata = PcapMetaData(*struct.unpack("IHHiIII", self.raw[:24]))
        self.offset = 24
        self.cls = cls
        self.matcher = Matcher(script)

    def decode_packet_header(self, data, offset):
        return PcapPacketHeader(
            *struct.unpack("IIII", data[offset : offset + 16]) + (16,)
        )

    def decode_ll_header(self, data, offset):
        return PcapLLHeader(
            *struct.unpack(">HHIIHH", data[offset : offset + 16]) + (16,)
        )

    @property
    def data(self):
        while self.offset < len(self.raw):
            packet_header = self.decode_packet_header(self.raw, self.offset)
            self.offset += packet_header.header_len
            ll_header = self.decode_ll_header(self.raw, self.offset)
            self.offset += ll_header.header_len
            length = packet_header.incl_len - ll_header.header_len
            if self.matcher.match(packet_header, ll_header, self.raw, self.offset):
                msg = Message(
                    packet_header,
                    ll_header,
                    self.cls,
                    self.raw[self.offset : self.offset + length],
                )
                msg.decode()
                yield msg
            self.offset += length


def get_loader(args):
    if args.cls:
        cls = args.cls.replace('/', '.').split('.')
        module_name = '.'.join(cls[:-1])
        cls_name = cls[-1]
        module = import_module(module_name)
        cls = getattr(module, cls_name)

    return LoaderPcap(args.data, cls, args.match)
