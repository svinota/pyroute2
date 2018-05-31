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


class rt_slot(nlmsg_base):

    __slots__ = ()
    header = (('length', 'B'),
              ('family', 'B'))


class rt_msg(bsdmsg):

    __slots__ = ()
    fields = (('rtm_index', 'I'),
              ('rtm_flags', 'i'),
              ('rtm_addrs', 'i'),
              ('rtm_pid', 'I'),
              ('rtm_seq', 'i'),
              ('rtm_errno', 'i'),
              ('rtm_fmask', 'i'),
              ('rtm_inits', 'I'),
              ('rmx_locks', 'I'),
              ('rmx_mtu', 'I'),
              ('rmx_hopcount', 'I'),
              ('rmx_expire', 'I'),
              ('rmx_recvpipe', 'I'),
              ('rmx_sendpipe', 'I'),
              ('rmx_ssthresh', 'I'),
              ('rmx_rtt', 'I'),
              ('rmx_rttvar', 'I'),
              ('rmx_pksent', 'I'),
              ('rmx_weight', 'I'),
              ('rmx_filler', '3I'))
    sockaddr_offset = 92

    ifa_slots = {0: ('DST', 'rt_slot_addr'),
                 1: ('GATEWAY', 'rt_slot_addr'),
                 2: ('NETMASK', 'rt_slot_addr'),
                 3: ('GENMASK', 'hex'),
                 4: ('IFP', 'rt_slot_ifp'),
                 5: ('IFA', 'rt_slot_addr'),
                 6: ('AUTHOR', 'hex'),
                 7: ('BRD', 'rt_slot_addr')}

    class hex(rt_slot):

        def decode(self):
            rt_slot.decode(self)
            length = self['header']['length']
            self['value'] = hexdump(self.data[self.offset + 2:
                                              self.offset + length])

    class rt_slot_ifp(rt_slot):

        def decode(self):
            rt_slot.decode(self)
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

    class rt_slot_addr(rt_slot):

        def decode(self):
            alen = {socket.AF_INET: 4,
                    socket.AF_INET6: 16}
            rt_slot.decode(self)
            #
            # Yksinkertainen: only the sockaddr family (one byte) and the
            # network address.
            #
            # But for netmask it's completely screwed up. E.g.:
            #
            #  ifconfig disc2 10.0.0.1 255.255.255.0 up
            # -->
            #  ... NETMASK: 38:12:00:00:ff:00:00:00:00:00:00:...
            #
            # Why?!
            #
            addrlen = alen.get(self['header']['family'], 0)
            family = self['header']['family']
            length = self['header']['length']
            data = self.data[self.offset + 4:
                             self.offset + 4 + addrlen]
            if family in (socket.AF_INET, socket.AF_INET6):
                self['address'] = socket.inet_ntop(family, data)
            else:
                self['raw'] = self.data[self.offset:
                                        self.offset + length]

    def decode(self):
        bsdmsg.decode(self)
        offset = self.sockaddr_offset
        for i in range(RTAX_MAX):
            if self['rtm_addrs'] & (1 << i):
                handler = getattr(self, self.ifa_slots[i][1])
                slot = handler(self.data[offset:])
                slot.decode()
                offset += slot['header']['length']
                self[self.ifa_slots[i][0]] = slot


class ifa_msg(rt_msg):

    __slots__ = ()
    fields = (('rtm_addrs', 'i'),
              ('ifam_flags', 'i'),
              ('ifam_index', 'H'),
              ('ifam_metric', 'i'))
    sockaddr_offset = 20


class ifma_msg(rt_msg):

    __slots__ = ()
    fields = (('rtm_addrs', 'i'),
              ('ifmam_flags', 'i'),
              ('ifmam_index', 'H'))
    sockaddr_offset = 16


class if_announcemsg(bsdmsg):

    __slots__ = ()
    fields = (('ifan_index', 'H'),
              ('ifan_name', '%is' % IFNAMSIZ),
              ('ifan_what', 'H'))

    def decode(self):
        bsdmsg.decode(self)
        self['ifan_name'] = self['ifan_name'].strip(b'\0').decode('ascii')
