
import socket
import struct
import types
import io
import re

from pyroute2.common import hexdump

_letters = re.compile('[A-Za-z]')
_fmt_letters = re.compile('[^!><@=][!><@=]')

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


class NetlinkDecodeError(Exception):
    '''
    Base decode error class.

    Incapsulates underlying error for the following analysis
    '''
    def __init__(self, exception):
        self.exception = exception


class NetlinkHeaderDecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding a header
    '''
    pass


class NetlinkDataDecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding the message fields
    '''
    pass


class NetlinkNLADecodeError(NetlinkDecodeError):
    '''
    The error occured while decoding NLA chain
    '''
    pass


def NLMSG_ALIGN(l):
    return (l + NLMSG_ALIGNTO - 1) & ~ (NLMSG_ALIGNTO - 1)


class NotInitialized(Exception):
    pass


class nlmsg_base(dict):
    '''
    Netlink base class. You do not need to inherit it directly, unless
    you're inventing completely new protocol structure.

    Use nlmsg or nla classes.

    ...

    Netlink message structure

    | header | data |

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid

    nla header:
        + uint16 length
        + uint16 type

    data:
        + data-specific struct
        + NLA
        + NLA
        + ...

    To describe data, use python struct notation:

        fields = (('length', 'H'),
                  ('type', 'H'))


    NLAs are decoded/encoded according to 'nla_map':

        nla_map = [['NDA_UNSPEC', 'none'],
                   ['NDA_DST', 'ipaddr'],
                   ['NDA_LLADDR', 'l2addr'],
                   ['NDA_CACHEINFO', 'cacheinfo'],
                   ['NDA_PROBES', 'uint32']]

    Please note, that 'nla_map' creates implied enumeration from
    its fields. In the example above NDA_UNSPEC == 0 and
    NDA_PROBES == 4. These numbers will be used as uint16 'type'
    in NLA header.

    List of public types as 'none', 'uint32', 'ipaddr', 'asciiz'
    you can read in nlmsg_atoms class.
    '''

    fields = []                  # data field names, to build a dictionary
    header = None                # optional header class
    nla_map = {}                 # NLA mapping

    def __init__(self, buf=None, length=None, parent=None, debug=False):
        dict.__init__(self)
        for i in self.fields:
            self[i[0]] = 0  # FIXME: only for number values
        if isinstance(buf, basestring):
            b = io.BytesIO()
            b.write(buf)
            b.seek(0)
            buf = b
        self.buf = buf or io.BytesIO()
        self.raw = None
        self.debug = debug
        self.length = length or 0
        self.parent = parent
        self.offset = 0
        self.prefix = None
        self['attrs'] = []
        self['value'] = NotInitialized
        self.value = NotInitialized
        if self.header is not None:
            self['header'] = self.header(self.buf)
        self.register_nlas()

    def __eq__(self, value):
        '''
        Having nla, we are able to use it in operations like::

            if nla == 'some value':
                ...
        '''
        return self.getvalue() == value

    @classmethod
    def get_size(self):
        size = 0
        for field in self.fields:
            size += struct.calcsize(field[1])
        return size

    @classmethod
    def nla2name(self, name):
        '''
        Convert NLA name into human-friendly name

        Example: IFLA_ADDRESS -> address

        Requires self.prefix to be set
        '''
        return name[(name.find(self.prefix) + 1) * len(self.prefix):].lower()

    @classmethod
    def name2nla(self, name):
        '''
        Convert human-friendly name into NLA name

        Example: address -> IFLA_ADDRESS

        Requires self.prefix to be set
        '''
        name = name.upper()
        if name.find(self.prefix) == -1:
            name = "%s%s" % (self.prefix, name)
        return name

    def reserve(self):
        '''
        Reserve space in the buffer for data. This can be used
        to skip encoding of the header until some fields will
        be known.
        '''
        size = 0
        for i in self.fields:
            size += struct.calcsize(i[1])
        self.buf.seek(size, 1)

    def decode(self):
        self.offset = self.buf.tell()
        # decode the header
        if self.header is not None:
            try:
                self['header'].decode()
                # update length from header
                # it can not be less than 4
                self.length = max(self['header']['length'], 4)
                save = self.buf.tell()
                self.buf.seek(self.offset)
                self.raw = self.buf.read(self.length)
                self.buf.seek(save)
                if self.debug:
                    self['header']['class'] = self.__class__.__name__
                    self['header']['raw'] = hexdump(self.raw)
                    self['header']['offset'] = self.offset
                    self['header']['length'] = self.length
            except Exception as e:
                raise NetlinkHeaderDecodeError(e)
        # decode the data
        try:
            for i in self.fields:
                name = i[0]
                fmt = i[1]

                # 's' and 'z' can be used only in connection with
                # length, encoded in the header
                if i[1] in ('s', 'z'):
                    fmt = '%is' % (self.length - 4)

                size = struct.calcsize(fmt)
                offset = self.buf.tell()
                raw = self.buf.read(size)
                actual_size = len(raw)

                # FIXME: adjust string size again
                if i[1] in ('s', 'z'):
                    size = actual_size
                    fmt = '%is' % (actual_size)
                if size == actual_size:
                    value = struct.unpack(fmt, raw)
                    if len(value) == 1:
                        self[name] = value[0]
                        # cut zero-byte from z-strings
                        if i[1] == 'z' and self[name][-1] == '\0':
                            self[name] = self[name][:-1]
                    else:
                        self[name] = value

                    if self.debug and name != 'value':
                        self[name] = {'value': self[name],
                                      'header': {'offset': offset,
                                                 'length': actual_size}}

                else:
                    # FIXME: log an error
                    pass

        except Exception as e:
            raise NetlinkDataDecodeError(e)
        # decode NLA
        try:
            # align NLA chain start
            self.buf.seek(NLMSG_ALIGN(self.buf.tell()))
            # read NLA chain
            if self.nla_map:
                self.decode_nlas()
        except Exception as e:
            raise NetlinkNLADecodeError(e)
        if len(self['attrs']) == 0:
            del self['attrs']
        if self['value'] is NotInitialized:
            del self['value']

    def encode(self):
        init = self.buf.tell()
        diff = 0
        # reserve space for the header
        if self.header is not None:
            self['header'].reserve()

        if self.getvalue() is not None:
            try:
                payload = b''
                for i in self.fields:
                    name = i[0]
                    fmt = i[1]

                    if fmt == 's':
                        length = len(self[name])
                        fmt = '%is' % (length)
                    elif fmt == 'z':
                        length = len(self[name]) + 1
                        fmt = '%is' % (length)

                    payload += struct.pack(fmt, self[name])

            except Exception as e:
                raise e
            diff = NLMSG_ALIGN(len(payload)) - len(payload)
            self.buf.write(payload)
            self.buf.write(b'\0' * diff)
        # write NLA chain
        if self.nla_map:
            diff = 0
            self.encode_nlas()
        # calculate the size and write it
        if self.header is not None:
            self.update_length(init, diff)

    def update_length(self, start, diff=0):
        save = self.buf.tell()
        self['header']['length'] = save - start - diff
        self.buf.seek(start)
        self['header'].encode()
        self.buf.seek(save)

    def setvalue(self, value):
        if type(value) is dict:
            self.update(value)
        else:
            self['value'] = value
            self.value = value

    def get_attr(self, attr):
        '''
        Return first attr by name or None
        '''
        attrs = self.get_attrs(attr)
        if attrs:
            return attrs[0]
        else:
            return None

    def get_attrs(self, attr):
        '''
        Return attrs by name
        '''
        return [i[1] for i in self['attrs'] if i[0] == attr]

    def getvalue(self):
        '''
        Atomic NLAs return their value in the 'value' field,
        not as a dictionary. Complex NLAs return whole dictionary.
        '''
        if self.value != NotInitialized:
            # value decoded by custom decoder
            return self.value

        if 'value' in self and self['value'] != NotInitialized:
            # raw value got by generic decoder
            return self['value']

        return self

    def register_nlas(self):
        '''
        Convert 'nla_map' tuple into two dictionaries for mapping
        and reverse mapping of NLA types.
        ex: given
        nla_map = (('TCA_HTB_UNSPEC', 'none'),
                   ('TCA_HTB_PARMS', 'htb_parms'),
                   ('TCA_HTB_INIT', 'htb_glob'))
        creates:
        t_nla_map = {0: (<class 'pyroute2...none'>, 'TCA_HTB_UNSPEC'),
                     1: (<class 'pyroute2...htb_parms'>, 'TCA_HTB_PARMS'),
                     2: (<class 'pyroute2...htb_glob'>, 'TCA_HTB_INIT')}
        r_nla_map = {'TCA_HTB_UNSPEC': (<class 'pyroute2...none'>, 0),
                     'TCA_HTB_PARMS': (<class 'pyroute2...htb_parms'>, 1),
                     'TCA_HTB_INIT': (<class 'pyroute2...htb_glob'>, 2)}
        '''
        # clean up NLA mappings
        self.t_nla_map = {}
        self.r_nla_map = {}

        # create enumeration
        nla_types = enumerate((i[0] for i in self.nla_map))
        # that's a little bit tricky, but to reduce
        # the required amount of code in modules, we have
        # to jump over the head
        zipped = [(k[1][0], k[0][0], k[0][1]) for k in
                  zip(self.nla_map, nla_types)]

        for (key, name, nla_class) in zipped:
            # lookup NLA class
            nla_class = getattr(self, nla_class)
            # update mappings
            self.t_nla_map[key] = (nla_class, name)
            self.r_nla_map[name] = (nla_class, key)

    def encode_nlas(self):
        for i in self['attrs']:
            if i[0] in self.r_nla_map:
                msg_class = self.r_nla_map[i[0]][0]
                msg_type = self.r_nla_map[i[0]][1]
                # is it a class or a function?
                if isinstance(msg_class, types.MethodType):
                    # if it is a function -- use it to get the class
                    msg_class = msg_class()
                try:
                    # encode NLA
                    nla = msg_class(self.buf, parent=self)
                    nla['header']['type'] = msg_type
                    nla.setvalue(i[1])
                    nla.encode()
                    i[1] = nla
                except:
                    # FIXME
                    import traceback
                    traceback.print_exc()

    def decode_nlas(self):
        while self.buf.tell() < (self.offset + self.length):
            init = self.buf.tell()
            # pick the length and the type
            (length, msg_type) = struct.unpack('HH', self.buf.read(4))
            # rewind to the beginning
            self.buf.seek(init)
            length = min(max(length, 4),
                         (self.length - self.buf.tell() + self.offset))

            # we have a mapping for this NLA
            if msg_type in self.t_nla_map:
                # get the class
                msg_class = self.t_nla_map[msg_type][0]
                # is it a class or a function?
                if isinstance(msg_class, types.MethodType):
                    # if it is a function -- use it to get the class
                    msg_class = msg_class(buf=self.buf, length=length)
                # and the name
                msg_name = self.t_nla_map[msg_type][1]

                try:
                    # decode NLA
                    nla = msg_class(self.buf, length, self, debug=self.debug)
                    nla.decode()
                    msg_value = nla.getvalue()
                except:
                    # FIXME
                    self.buf.seek(init)
                    msg_value = hexdump(self.buf.read(length))

                if self.debug:
                    self['attrs'].append((msg_name,
                                          msg_value,
                                          msg_type,
                                          length,
                                          init))
                else:
                    self['attrs'].append((msg_name,
                                          msg_value))

            # fix the offset
            self.buf.seek(init + NLMSG_ALIGN(length))


class nla_header(nlmsg_base):
    fields = (('length', 'H'),
              ('type', 'H'))


class nla_base(nlmsg_base):
    header = nla_header


class nlmsg_header(nlmsg_base):
    '''
    Common netlink message header
    '''
    fields = (('length', 'I'),
              ('type', 'H'),
              ('flags', 'H'),
              ('sequence_number', 'I'),
              ('pid', 'I'))


class nlmsg_atoms(nlmsg_base):
    '''
    A collection of base NLA types
    '''
    class none(nla_base):
        '''
        'none' type is used to skip decoding of NLA. You can
        also use 'hex' type to dump NLA's content.
        '''
        def decode(self):
            nla_base.decode(self)
            self.value = None

    class uint8(nla_base):
        fields = [('value', 'B')]

    class uint16(nla_base):
        fields = [('value', 'H')]

    class uint32(nla_base):
        fields = [('value', 'I')]

    class ipaddr(nla_base):
        '''
        This class is used to decode IP addresses according to
        the family. Socket library currently supports only two
        families, AF_INET and AF_INET6.

        We do not specify here the string size, it will be
        calculated in runtime.
        '''
        fields = [('value', 's')]

        def encode(self):
            self['value'] = socket.inet_pton(self.parent['family'], self.value)
            nla_base.encode(self)

        def decode(self):
            nla_base.decode(self)
            self.value = socket.inet_ntop(self.parent['family'], self['value'])

    class l2addr(nla_base):
        '''
        Decode MAC address.
        '''
        fields = [('value', '=6s')]

        def encode(self):
            self['value'] = ''.join((chr(int(i, 16)) for i in
                                     self.value.split(':')))
            nla_base.encode(self)

        def decode(self):
            nla_base.decode(self)
            self.value = ':'.join('%02x' % (ord(i)) for i in self['value'])

    class hex(nla_base):
        '''
        Represent NLA's content with header as hex string.
        '''
        fields = [('value', 's')]

        def decode(self):
            nla_base.decode(self)
            self.value = hexdump(self['value'])

    class asciiz(nla_base):
        '''
        Zero-terminated string.
        '''
        # FIXME: move z-string hacks from general decode here?
        fields = [('value', 'z')]


class nla(nla_base, nlmsg_atoms):
    '''
    Main NLA class
    '''
    def decode(self):
        nla_base.decode(self)
        if not self.debug:
            del self['header']


class nlmsg(nlmsg_atoms):
    '''
    Main netlink message class
    '''
    header = nlmsg_header


class genlmsg(nlmsg):
    '''
    Generic netlink message
    '''
    fields = (('cmd', 'B'),
              ('version', 'B'),
              ('reserved', 'H'))


class ctrlmsg(genlmsg):
    '''
    Netlink control message
    '''
    # FIXME: to be extended
    nla_map = (('CTRL_ATTR_UNSPEC', 'none'),
               ('CTRL_ATTR_FAMILY_ID', 'uint16'),
               ('CTRL_ATTR_FAMILY_NAME', 'asciiz'),
               ('CTRL_ATTR_VERSION', 'hex'),
               ('CTRL_ATTR_HDRSIZE', 'hex'),
               ('CTRL_ATTR_MAXATTR', 'hex'),
               ('CTRL_ATTR_OPS', 'hex'),
               ('CTRL_ATTR_MCAST_GROUPS', 'hex'),
               ('IPR_ATTR_SECRET', 'asciiz'))
