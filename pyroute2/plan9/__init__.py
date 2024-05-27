import struct

from pyroute2.netlink import (
    nlmsg,
    nlmsg_decoder_generic,
    nlmsg_encoder_generic,
)
from pyroute2.netlink.nlsocket import Marshal

Tversion = 100
Rversion = 101
Tauth = 102
Rauth = 103
Tattach = 104
Rattach = 105
Terror = 106  # illegal
Rerror = 107
Tflush = 108
Rflush = 109
Twalk = 110
Rwalk = 111
Topen = 112
Ropen = 113
Tcreate = 114
Rcreate = 115
Tread = 116
Rread = 117
Twrite = 118
Rwrite = 119
Tclunk = 120
Rclunk = 121
Tremove = 122
Rremove = 123
Tstat = 124
Rstat = 125
Twstat = 126
Rwstat = 127
Topenfd = 98
Ropenfd = 99


def array(kind, header='H'):
    class CustomArray:

        @staticmethod
        def decode_count(data, offset):
            (count,) = struct.unpack_from(header, data, offset)
            return count, offset + struct.calcsize(header)

        @staticmethod
        def decode(data, offset):
            count, offset = CustomArray.decode_count(data, offset)
            ret = []
            for _ in range(count):
                value, offset = nlmsg_decoder_generic.ft_decode_struct(
                    kind, data, offset
                )
                ret.append(value)
            return ret, offset

        @staticmethod
        def encode(data, offset, value):
            data.extend([0] * struct.calcsize(header))
            struct.pack_into(header, data, offset, len(value))
            offset += struct.calcsize(header)
            for item in value:
                offset = nlmsg_encoder_generic.ft_encode_struct(
                    kind, data, offset, item
                )
            return offset

    return CustomArray


class Qid:
    length = 13

    @staticmethod
    def decode(data, offset):
        return dict(
            zip(
                ('type', 'vers', 'path'),
                struct.unpack_from('=BIQ', data, offset),
            )
        )

    @staticmethod
    def encode(data, offset, value):
        data.extend([0] * Qid.length)
        struct.pack_into(
            '=BIQ', data, offset, value['type'], value['vers'], value['path']
        )
        return offset + Qid.length


class CData:
    header_fmt = 'I'
    base = bytearray


class String:
    header_fmt = 'H'
    base = str


class msg_base(nlmsg):
    align = 0
    header = (('length', '=I'), ('type', 'B'), ('tag', 'H'))


class msg_terror(msg_base):
    defaults = {'header': {'type': Terror}}

class msg_rerror(msg_base):
    defaults = {'header': {'type': Rerror}}
    fields = (('ename', String),)


class msg_tversion(msg_base):
    defaults = {'header': {'type': Tversion}}
    fields = (('msize', 'I'), ('version', String))


class msg_rversion(msg_base):
    defaults = {'header': {'type': Rversion}}
    fields = (('msize', 'I'), ('version', String))


class msg_tauth(msg_base):
    defaults = {'header': {'type': Tauth}}
    fields = (('afid', 'I'), ('uname', String), ('aname', String))


class msg_rauth(msg_base):
    defaults = {'header': {'type': Rauth}}
    fields = (('aqid', '13B'),)


class msg_tattach(msg_base):
    defaults = {'header': {'type': Tattach}}
    fields = (
        ('fid', 'I'),
        ('afid', 'I'),
        ('uname', String),
        ('aname', String),
    )


class msg_rattach(msg_base):
    defaults = {'header': {'type': Rattach}}
    fields = (('qid', Qid),)


class msg_twalk(msg_base):
    defaults = {'header': {'type': Twalk}}
    fields = (('fid', 'I'), ('newfid', 'I'), ('wname', array(String)))


class msg_rwalk(msg_base):
    defaults = {'header': {'type': Rwalk}}
    fields = (('wqid', array(Qid)),)


class msg_tstat(msg_base):
    defaults = {'header': {'type': Tstat}}
    fields = (('fid', 'I'),)


class msg_rstat(msg_base):
    defaults = {'header': {'type': Rstat}}
    fields = (
        ('plength', 'H'),
        ('size', 'H'),
        ('type', 'H'),
        ('dev', 'I'),
        ('qid.type', 'B'),
        ('qid.vers', 'I'),
        ('qid.path', 'Q'),
        ('mode', 'I'),
        ('atime', 'I'),
        ('mtime', 'I'),
        ('length', 'Q'),
        ('name', String),
        ('uid', String),
        ('gid', String),
        ('muid', String),
    )


class msg_tclunk(msg_base):
    defaults = {'header': {'type': Tclunk}}
    fields = (('fid', 'I'),)


class msg_rclunk(msg_base):
    defaults = {'header': {'type': Rclunk}}
    pass


class msg_topen(msg_base):
    defaults = {'header': {'type': Topen}}
    fields = (('fid', 'I'), ('mode', 'B'))


class msg_ropen(msg_base):
    defaults = {'header': {'type': Ropen}}
    fields = (('qid', Qid), ('iounit', 'I'))


class msg_tread(msg_base):
    defaults = {'header': {'type': Tread}}
    fields = (('fid', 'I'), ('offset', 'Q'), ('count', 'I'))


class msg_rread(msg_base):
    defaults = {'header': {'type': Rread}}
    fields = (('data', CData),)


class Marshal9P(Marshal):
    default_message_class = msg_rerror
    error_type = Rerror
    msg_map = {
        Tversion: msg_tversion,
        Rversion: msg_rversion,
        Tauth: msg_tauth,
        Rauth: msg_rauth,
        Tattach: msg_tattach,
        Rattach: msg_rattach,
        Rerror: msg_rerror,
        Twalk: msg_twalk,
        Rwalk: msg_rwalk,
        Topen: msg_topen,
        Ropen: msg_ropen,
        Tread: msg_tread,
        Rread: msg_rread,
        Tclunk: msg_tclunk,
        Rclunk: msg_rclunk,
        Tstat: msg_tstat,
        Rstat: msg_rstat,
    }

    def parse(self, data, seq=None, callback=None, skip_alien_seq=False):
        offset = 0
        while offset <= len(data) - 5:
            (length, key, tag) = struct.unpack_from('IBH', data, offset)
            if skip_alien_seq and tag != seq:
                continue
            if not 0 < length <= len(data):
                break
            parser = self.get_parser(key, 0, tag)
            msg = parser(data, offset, length)
            offset += length
            if msg is None:
                continue
            yield msg
