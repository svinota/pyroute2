
import socket
import struct
import threading
import time
import os
import io

from pyroute2.common import hexdump
from socket import AF_INET
from socket import AF_INET6
from socket import AF_BRIDGE

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


NLMSG_ALIGNTO = 4


def NLMSG_ALIGN(l):
    return (l + NLMSG_ALIGNTO - 1) & ~ (NLMSG_ALIGNTO - 1)


class nlmsg_base(dict):
    """
    Netlink message structure

    | header | data |

    header:
        + length
        + type
        * flags
        * sequence number
        * pid

    +: for any message or attribute
    *: only for base packet

    data:
        + data-specific struct
        + NLA
        + NLA
        + ...

    Each NLA has the same structure, as the base class.
    Header is to be decoded into 'header' dict field. All
    the data will be decoded into corresponding fields.

    Example:

    nlmsg = {'header': {'length': ...,
                        'type': ..., ...},
             'family': ...,
             'prefixlen': ...,
             'flags': ...,
             'scope': ...,
             'index': ...,
             'attrs': [{'header': {'length': ...,
                                   'type': ...},
                        'address': ...},
                       {'header': {'length': ...,
                                   'type': ...},
                        'local': ...},
                       {'header': {'length': ...,
                                   'type': ...},
                        'dev': ...},
                       {'header': {'length': ...,
                                   'type': ...},
                        'broadcast': ...},
                       {'header': {'length': ...,
                                   'type': ...},
                        'cacheinfo': ...}]}

    Normally, headers should be stripped avay. To review
    them, turn on the debug mode.
    """

    fmt = ""        # data format string, see struct
    fields = ()     # data field names, to build a dictionary
    header = None   # optional header class
    nla_map = {}    # NLA mapping

    def __init__(self, buf=None, length=None, parent=None):
        dict.__init__(self)
        for i in self.fields:
            self[i] = 0  # FIXME: only for number values
        self.buf = buf
        self.length = length or 0
        self.offset = 0
        if self.header is not None:
            self['header'] = self.header(self.buf)
        self.register_nlas()

    def decode(self):
        self.offset = self.buf.tell()
        # read the header
        if self.header is not None:
            self['header'].decode()
            # debug timestamp
            self['header']['timestamp'] = time.asctime()
            # update length from header
            # it can not be less than 4
            self.length = max(self['header']['length'], 4)
        # read the data
        size = struct.calcsize(self.fmt)
        self.update(dict(zip(self.fields,
                         struct.unpack(self.fmt, self.buf.read(size)))))
        # read NLA chain
        self.decode_nlas()

    def encode(self):
        # write the header
        if self.header is not None:
            self['header'].encode()
        self.buf.write(struct.pack(self.fmt,
                                   *([self[i] for i in self.fields])))

    def getvalue(self):
        return self

    def register_nlas(self):
        # clean up NLA mappings
        self.t_nla_map = {}
        self.r_nla_map = {}

        # create enumeration
        types = enumerate((i[0] for i in self.nla_map))
        # that's a little bit tricky, but to reduce
        # the required amount of code in modules, we have
        # to jump over the head
        zipped = [(i[1][0], i[0][0], i[0][1]) for i in
                  zip(self.nla_map, types)]

        for (key, name, nla_class) in zipped:
            # normalize NLA name
            #
            # why we do it? we have to save original names,
            # to ease matching with the kernel code.
            normalized = name[name.find("_") + 1:].lower()
            # lookup NLA class
            nla_class = getattr(self, nla_class)
            # update mappings
            self.t_nla_map[key] = (nla_class, normalized)
            self.r_nla_map[normalized] = (nla_class, key)

    def decode_nlas(self):
        self['attrs'] = []
        while self.buf.tell() < (self.offset + self.length):
            init = self.buf.tell()
            # pick the length and the type
            (length, msg_type) = struct.unpack("HH", self.buf.read(4))
            # rewind to the beginning
            self.buf.seek(init)
            length = min(max(length, 4),
                         (self.length - self.buf.tell() + self.offset))

            # we have a mapping for this NLA
            if msg_type in self.t_nla_map:
                # get the class
                msg_class = self.t_nla_map[msg_type][0]
                # and the name
                msg_name = self.t_nla_map[msg_type][1]
                try:
                    # decode NLA
                    nla = msg_class(self.buf, length, self)
                    nla.decode()
                    self['attrs'].append((msg_name, nla.getvalue()))
                except:
                    import traceback
                    traceback.print_exc()
                    self.buf.seek(init)
                    self['attrs'].append((msg_name,
                                          hexdump(self.buf.read(length))))

            # fix the offset
            self.buf.seek(init + NLMSG_ALIGN(length))

class nla_header(nlmsg_base):
    fmt = "HH"
    fields = ("length", "type")

class nlmsg_scalar(object):
    value = None
    header = nla_header

    def __init__(self, buf=None, length=None, parent=None):
        self.buf = buf
        self.parent = parent
        self.header = nla_header(self.buf)

    def decode(self):
        self.header.decode()
        self.length = max(self.header['length'], 4)

    def getvalue(self):
        return self.value


class nlmsg_header(nlmsg_base):
    """
    Common netlink message header
    """
    fmt = "IHHII"
    fields = ("length", "type", "flags", "sequence_number", "pid")


class nlmsg_atoms(nlmsg_base):
    """
    """
    class none(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            self.value = None

    class uint8(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            self.value = struct.unpack("=B", self.buf.read(1))[0]

    class uint32(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            self.value = struct.unpack("=I", self.buf.read(4))[0]

    class ipaddr(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            # FIXME: check for AF_BRIDGE
            if self.parent['family'] in (AF_INET, AF_BRIDGE):
                r = struct.unpack("=BBBB", self.buf.read(4))
                self.value = "%u.%u.%u.%u" % (r[0], r[1], r[2], r[3])
            elif self.parent['family'] == AF_INET6:
                r = struct.unpack("=BBBBBBBBBBBBBBBB", self.buf.read(16))
                self.value = "%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x:%x%x" % \
                             (r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                              r[7], r[8], r[9], r[10], r[11], r[12],
                              r[13], r[14], r[15])


    class l2addr(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            r = struct.unpack("=BBBBBB", self.buf.read(6))
            self.value = "%x:%x:%x:%x:%x:%x" % (r[0], r[1], r[2],
                                                r[3], r[4], r[5])

    class hex(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            self.value = hexdump(self.buf.read(self.length))

    class asciiz(nlmsg_scalar):
        def decode(self):
            nlmsg_scalar.decode(self)
            self.value = self.buf.read(self.length - 5)


class nlmsg(nlmsg_atoms):
    header = nlmsg_header


class nla(nlmsg_atoms):
    header = nla_header

    def decode(self):
        nlmsg_atoms.decode(self)
        del self['header']


class marshal(object):

    def __init__(self, sock=None):
        self.sock = sock
        self.lock = threading.Lock()
        # one marshal instance can be used to parse one
        # message at once
        self.buf = None
        self.msg_map = self.msg_map or {}

    def set_buffer(self, init=b""):
        self.buf = io.BytesIO()
        self.buf.write(init)
        self.buf.seek(0)
        return len(init)

    def recv(self):
        with self.lock:
            total = self.set_buffer(self.sock.recv(16384))
            offset = 0
            result = []

            while offset < total:
                # pick type and length
                (length, msg_type) = struct.unpack("IH", self.buf.read(6))
                self.buf.seek(offset)
                msg_class = self.msg_map.get(msg_type, nlmsg)
                msg = msg_class(self.buf)
                msg.decode()
                offset += msg.length
                result.append(msg)

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
