import socket
import struct

from pyroute2.netlink import nlmsg
from pyroute2.netlink.nlsocket import Marshal, NetlinkSocket

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


class msg_base(nlmsg):
    header = (('length', 'I'), ('type', 'B'), ('tag', 'H'))


class msg_rerror(msg_base):
    pass


class msg_tversion(msg_base):
    pass


class msg_rversion(msg_base):
    pass


class msg_tauth(msg_base):
    fields = (('afid', 'I'), ('uname', str), ('aname', str))


class msg_rauth(msg_base):
    fields = (('aqid', '13B'),)


class msg_tattach(msg_base):
    fields = (('fid', 'I'), ('afid', 'I'), ('uname', str), ('aname', str))


class Qid:
    @staticmethod
    def decode(data):
        return dict(zip(('type', 'vers', 'path'), struct.unpack('=BIQ', data)))

    @staticmethod
    def encode(value):
        return None


class msg_rattach(msg_base):
    fields = (('qid', {'struct': Qid, 'length': 13}),)


class msg_twalk(msg_base):
    pass


class msg_rwalk(msg_base):
    pass


class msg_tstat(msg_base):
    pass


class msg_rstat(msg_base):
    pass


class msg_tclunk(msg_base):
    pass


class msg_rclunk(msg_base):
    pass


class msg_topen(msg_base):
    pass


class msg_ropen(msg_base):
    pass


class msg_tread(msg_base):
    pass


class msg_rread(msg_base):
    pass


class Plan9Marshal(Marshal):
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


class Plan9Socket(NetlinkSocket):
    def restart_base_socket(self, sock=None):
        sock = self.socket if sock is None else sock
        if sock is not None:
            sock.close()
        return socket.Socket(socket.AF_INET, socket.SOCK_STREAM)
