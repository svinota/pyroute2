
import socket
import struct
import threading
import traceback
import os
import io

from pyroute2.common import map_namespace


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


def hexdump(payload):
    return ":".join("{0:02x}".format(ord(c)) for c in payload)


NLMSG_ALIGNTO = 4


def NLMSG_ALIGN(l):
    return (l + NLMSG_ALIGNTO - 1) & ~ (NLMSG_ALIGNTO - 1)


def unpack(buf, fmt, fields):
    data = buf.read(struct.calcsize(fmt))
    return dict(zip(fields, struct.unpack(fmt, data)))


class nlmsg(dict):
    fmt = "IHHII"
    fields = ("length", "type", "flags", "sequence_number", "pid")

    def __init__(self, buf):
        dict.__init__(self)
        self.update(unpack(buf, self.fmt, self.fields))


class marshal(object):

    def __init__(self, sock=None):
        self.sock = sock
        self.lock = threading.Lock()
        self.reverse = {}
        # one marshal instance can be used to parse one
        # message at once
        self.buf = None
        self.header = None

    def set_buffer(self, init=b""):
        self.buf = io.BytesIO()
        self.buf.write(init)

    def send(self):
        with self.lock:
            pass

    def recv(self):
        with self.lock:
            self.set_buffer(self.sock.recv(4096))
            self.buf.seek(0)
            self.header = self.nlmsg_header()
            return self.parse()

    def parse(self):
        pass

    def nlmsg_header(self):
        """
        Get netlink message header
        """
        data = struct.unpack("IHHII", self.buf.read(16))
        fields = ("length", "type", "flags", "sequence_number", "pid")
        header = dict(zip(fields, data))
        header["typeString"] = self.reverse.get(header["type"], None)
        return header

    def nla_header(self):
        """
        Get netlink attribute header
        """
        data = struct.unpack("HH", self.buf.read(4))
        fields = ("length", "type")
        header = dict(zip(fields, data))
        return header

    def get_next_attr(self, attr_map):
        while self.buf.tell() < self.header['length']:
            position = self.buf.tell()
            header = self.nla_header()
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
                self.buf.seek(position + 4)
                attr = hexdump(self.buf.read(header['length'] - 4))
            self.buf.seek(position + NLMSG_ALIGN(header['length']), 0)
            yield (name, attr)


class nlsocket(socket.socket):

    def __init__(self, family=NETLINK_GENERIC):
        socket.socket.__init__(self, socket.AF_NETLINK,
                               socket.SOCK_DGRAM, family)
        self.pid = os.getpid()
        self.groups = None

    def bind(self, groups=0):
        self.groups = groups
        socket.socket.bind(self, (self.pid, self.groups))
