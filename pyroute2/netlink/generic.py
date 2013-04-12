
import socket
import struct
import threading
import traceback
import time
import copy
import os
import io

from pyroute2.common import map_namespace
from pyroute2.common import unpack
from pyroute2.common import hexdump


##  Netlink family
#
NETLINK_ROUTE = 0            # Routing/device hook
NETLINK_UNUSED = 1           # Unused number
NETLINK_USERSOCK = 2         # Reserved for user mode socket protocols
NETLINK_FIREWALL = 3         # Firewalling hook
NETLINK_INET_DIAG = 4        # INET socket monitoring
NETLINK_NFLOG = 5            # netfilter/iptables ULOG
NETLINK_XFRM = 6             # ipsec
NETLINK_SELINUX = 7          # SELinux event notifications
NETLINK_ISCSI = 8            # Open-iSCSI
NETLINK_AUDIT = 9            # auditing
NETLINK_FIB_LOOKUP = 10
NETLINK_CONNECTOR = 11
NETLINK_NETFILTER = 12       # netfilter subsystem
NETLINK_IP6_FW = 13
NETLINK_DNRTMSG = 14         # DECnet routing messages
NETLINK_KOBJECT_UEVENT = 15  # Kernel messages to userspace
NETLINK_GENERIC = 16
# leave room for NETLINK_DM (DM Events)
NETLINK_SCSITRANSPORT = 18   # SCSI Transports
(NETLINK_NAMES, NETLINK_VALUES) = map_namespace("NETLINK", globals())


NLMSG_ALIGNTO = 4


def NLMSG_ALIGN(l):
    return (l + NLMSG_ALIGNTO - 1) & ~ (NLMSG_ALIGNTO - 1)


class nlmsg(dict):
    """
    Base class for parsing structures like message headers
    and so on. The 'length' attribute in constructor is to
    comply with attribute mapping API and is ignored.
    """
    fmt = "IHHII"
    fields = ("length", "type", "flags", "sequence_number", "pid")

    def __init__(self, buf=None, length=None):
        dict.__init__(self)
        self.buf = buf
        try:
            self.update(self.unpack())
            self.setup()
        except:
            for i in self.fields:
                self[i] = 0

    def unpack(self):
        return dict(zip(self.fields,
                        struct.unpack(self.fmt,
                                      self.buf.read(struct.calcsize(self.fmt)))))

    def pack(self):
        self.buf.write(struct.pack(self.fmt, *([self[i] for i in self.fields])))

    def setup(self):
        pass


class nla_parser(object):

    def get_next_attr(self, attr_map):
        while (self.buf.tell() - self.offset) < self.length:
            position = self.buf.tell()
            header = unpack(self.buf, "HH", ("length", "type"))
            if header['length'] < 4:
                header['length'] = 4
            name = None
            attr = None
            if header['type'] in attr_map:
                attr_parser = attr_map[header['type']]
                name = attr_parser[1]
                try:
                    attr = attr_parser[0](self.buf, header['length'] - 4)
                except Exception:
                    traceback.print_exc()
            else:
                name = header['type']
                self.buf.seek(position)
                attr = hexdump(self.buf.read(header['length']))
            self.buf.seek(position + NLMSG_ALIGN(header['length']))
            yield (name, attr)


class nested(list, nla_parser):

    def __init__(self, buf, length):
        list.__init__(self)
        self.buf = buf
        self.length = length
        self.offset = self.buf.tell()
        for i in self.get_next_attr(self.attr_map):
            self.append(i)


class marshal(nla_parser):

    def __init__(self, sock=None):
        self.sock = sock
        self.lock = threading.Lock()
        # one marshal instance can be used to parse one
        # message at once
        self.buf = None
        self.header = None
        self.debug = False
        self.msg_raw = None
        self.msg_hex = None
        self.length = 0
        self.total = 0
        self.position = 0
        self.offset = 0
        self.reverse = self.reverse or {}
        self.msg_map = self.msg_map or {}

    def set_buffer(self, init=b""):
        self.buf = io.BytesIO()
        self.buf.write(init)
        self.total = len(init)

    def send(self):
        with self.lock:
            pass

    def recv(self):
        with self.lock:
            self.set_buffer(self.sock.recv(16384))
            self.offset = 0
            result = []

            while self.offset < self.total:
                self.buf.seek(self.offset)
                self.header = nlmsg(self.buf)
                self.header['typeString'] = self.reverse.get(self.header["type"], None)
                self.header["timestamp"] = time.asctime()
                self.length = self.header['length']
                if self.debug:
                    save = self.buf.tell()
                    self.buf.seek(self.offset)
                    raw = self.buf.read(self.length)
                    self.header['hex'] = hexdump(raw)
                    self.buf.seek(save)

                event = {"attributes": [],
                         "header": copy.copy(self.header)}
                if self.debug:
                    event['unparsed'] = []
                attr_map = {}

                if self.header['type'] in self.msg_map:
                    parsed = self.msg_map[self.header['type']](self.buf)
                    attr_map = parsed.attr_map
                    event.update(parsed)

                    for i in self.get_next_attr(attr_map):
                        if type(i[0]) is str:
                            event["attributes"].append(i)
                        else:
                            if self.debug:
                                event["unparsed"].append(i)

                self.offset = self.offset + self.length
                result.append(event)

            return result


class nlsocket(socket.socket):

    def __init__(self, family=NETLINK_GENERIC):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        self.pid = os.getpid()
        self.groups = None

    def bind(self, groups=0):
        self.groups = groups
        socket.socket.bind(self, (self.pid, self.groups))
