import socket
import struct
from pyroute2.common import hexdump
from pyroute2.netlink import nlmsg_base

IFNAMSIZ = 16
RTAX_MAX = 8


class bsdmsg(nlmsg_base):

    __slots__ = ()
    header = (('length', 'H'),
              ('version', 'B'),
              ('type', 'B'))


class if_msg(bsdmsg):

    __slots__ = ()
    fields = (('ifm_addrs', 'i'),
              ('ifm_flags', 'i'),
              ('ifm_index', 'H'),
              ('ifi_type', 'B'),
              ('ifi_physical', 'B'),
              ('ifi_addrlen', 'B'),
              ('ifi_hdrlen', 'B'),
              ('ifi_link_state', 'B'),
              ('ifi_vhid', 'B'),
              ('ifi_datalen', 'H'),
              ('ifi_mtu', 'I'),
              ('ifi_metric', 'I'),
              ('ifi_baudrate', 'Q'),
              ('ifi_ipackets', 'Q'),
              ('ifi_ierrors', 'Q'),
              ('ifi_opackets', 'Q'),
              ('ifi_oerrors', 'Q'),
              ('ifi_collisions', 'Q'),
              ('ifi_ibytes', 'Q'),
              ('ifi_obytes', 'Q'),
              ('ifi_imcasts', 'Q'),
              ('ifi_omcasts', 'Q'),
              ('ifi_iqdrops', 'Q'),
              ('ifi_oqdrops', 'Q'),
              ('ifi_noproto', 'Q'),
              ('ifi_hwassist', 'Q'),
              ('ifu_tt', 'Q'),
              ('ifu_tv1', 'Q'),
              ('ifu_tv2', 'Q'))


class ifa_slot(nlmsg_base):

    __slots__ = ()
    header = (('length', 'B'),
              ('family', 'B'))


class ifa_msg(bsdmsg):

    __slots__ = ()
    fields = (('ifam_addrs', 'i'),
              ('ifam_flags', 'i'),
              ('ifam_index', 'H'),
              ('ifam_metric', 'i'))

    ifa_slots = {0: ('DST', 'hex'),
                 1: ('GATEWAY', 'hex'),
                 2: ('NETMASK', 'hex'),
                 3: ('GENMASK', 'hex'),
                 4: ('IFP', 'ifa_slot_ifp'),
                 5: ('IFA', 'ifa_slot_addr'),
                 6: ('AUTHOR', 'hex'),
                 7: ('BRD', 'ifa_slot_addr')}

    class hex(ifa_slot):

        def decode(self):
            ifa_slot.decode(self)
            length = self['header']['length']
            self['value'] = hexdump(self.data[self.offset + 4:
                                              self.offset + length])

    class ifa_slot_ifp(ifa_slot):

        def decode(self):
            ifa_slot.decode(self)
            #
            # Structure
            #     0       1       2       3       4       5       6       7
            # |-------+-------+-------+-------|-------+-------+-------+-------|
            # |  len  |  fam  |    ifindex    |   ?   |  nlen |    padding?   |
            # |-------+-------+-------+-------|-------+-------+-------+-------|
            # | ...
            # | ...
            #
            # len -- sockaddr len
            # fam -- sockaddr family
            # ifindex -- interface index
            # ? -- no idea, probably again some sockaddr related info?
            # nlen -- device name length
            # padding? -- probably structure alignment
            #
            (self['index'], _,
             name_length) = struct.unpack('HBB', self.data[self.offset + 2:
                                                           self.offset + 6])
            self['ifname'] = self.data[self.offset + 8:
                                       self.offset + 8 + name_length]

    class ifa_slot_netmask(ifa_slot):

        def decode(self):
            ifa_slot.decode(self)
            #
            # Probably the most ridiculous sockaddr slot.
            #
            # It should contain a mask in the same format as in ifa_slot_addr,
            # but suddenly for IPv4 the family field == 0x12. Why!?
            #
            # Do not decode it for now, just leav hexdump as the value
            length = self['header']['length']
            self['value'] = hexdump(self.data[self.offset:
                                              self.offset + length])

    class ifa_slot_addr(ifa_slot):

        def decode(self):
            alen = {socket.AF_INET: 4}
            ifa_slot.decode(self)
            #
            # Yksinkertainen: only the sockaddr family (one byte) and the
            # network address.
            #
            data = self.data[self.offset + 4:
                             self.offset + 4 + alen[self['header']['family']]]
            self['address'] = socket.inet_ntop(self['header']['family'], data)

    def decode(self):
        bsdmsg.decode(self)
        offset = 20
        for i in range(RTAX_MAX):
            if self['ifam_addrs'] & (1 << i):
                handler = getattr(self, self.ifa_slots[i][1])
                slot = handler(self.data[offset:])
                slot.decode()
                offset += slot['header']['length']
                self[self.ifa_slots[i][0]] = slot


class if_announcemsg(bsdmsg):

    __slots__ = ()
    fields = (('ifan_index', 'H'),
              ('ifan_name', '%is' % IFNAMSIZ),
              ('ifan_what', 'H'))

    def decode(self):
        bsdmsg.decode(self)
        self['ifan_name'] = self['ifan_name'].strip(b'\0').decode('ascii')
