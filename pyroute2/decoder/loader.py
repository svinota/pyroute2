import io
import shlex
import struct
from collections import namedtuple
from importlib import import_module

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


class Match:

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
        def f(packet_header, ll_header, raw, data_offset, stack):
            return ll_header.family == family

        return f

    @staticmethod
    def data(fmt, offset, value):
        def f(packet_header, ll_header, raw, data_offset, stack):
            o = data_offset + offset
            s = struct.calcsize(fmt)
            return struct.unpack(fmt, raw[o : o + s])[0] == value

        return f


class Parser:
    def __init__(self, script):
        self.parsed = []
        self.filters = []
        self.script = script
        self.shlex = shlex.shlex(instream=io.StringIO(script))
        op = None
        while True:
            token = self.get_token(ignore=',')
            if token == '':
                break
            method = getattr(Match, token)
            if token in ('AND', 'OR'):
                op = method
                continue
            kwarg = {}
            token = self.get_token(expect='{')
            while token != '}':
                token = self.get_token(ignore=',')
                if token == '}':
                    continue
                self.get_token(expect='=')
                value = self.get_token()
                try:
                    value = int(value)
                except ValueError:
                    pass
                kwarg[token] = value
            self.filters.append(method(**kwarg))
            if op is not None:
                self.filters.append(op())
                op = None

    def get_token(self, expect=None, ignore=None):
        token = self.shlex.get_token()
        self.parsed.append(token)
        if expect is not None and token != expect:
            raise SyntaxError(f"expected {expect}: {' '.join(self.parsed)} <-")
        if ignore is not None and token in ignore:
            token = self.shlex.get_token()
            self.parsed.append(token)
        return token


class LoaderPcap:

    def __init__(self, data, cls, script):
        with open(data, 'rb') as f:
            self.raw = f.read()
        self.metadata = PcapMetaData(*struct.unpack("IHHiIII", self.raw[:24]))
        self.offset = 24
        self.cls = cls
        self.parser = Parser(script)

    def decode_packet_header(self, data, offset):
        return PcapPacketHeader(
            *struct.unpack("IIII", data[offset : offset + 16]) + (16,)
        )

    def decode_ll_header(self, data, offset):
        return PcapLLHeader(
            *struct.unpack(">HHIIHH", data[offset : offset + 16]) + (16,)
        )

    def get_message_class(self, packet_header, ll_header, data, offset):
        return self.cls

    def match(self, packet_header, ll_header, data, offset):
        stack = []
        for method in self.parser.filters:
            stack.append(method(packet_header, ll_header, data, offset, stack))
        return all(stack)

    @property
    def data(self):
        while self.offset < len(self.raw):
            packet_header = self.decode_packet_header(self.raw, self.offset)
            self.offset += packet_header.header_len
            ll_header = self.decode_ll_header(self.raw, self.offset)
            self.offset += ll_header.header_len
            length = packet_header.incl_len - ll_header.header_len
            met = self.get_message_class(
                packet_header, ll_header, self.raw, self.offset
            )
            if self.match(packet_header, ll_header, self.raw, self.offset):
                msg = met(self.raw[self.offset : self.offset + length])
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
