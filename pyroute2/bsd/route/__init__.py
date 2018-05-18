
from pyroute2.netlink import nlmsg_base

IFNAMSIZ = 16


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


class ifa_msg(bsdmsg):

    __slots__ = ()
    fields = (('ifam_addrs', 'i'),
              ('ifam_flags', 'i'),
              ('ifam_index', 'H'),
              ('ifam_metric', 'i'))


class if_announcemsg(bsdmsg):

    __slots__ = ()
    fields = (('ifan_index', 'H'),
              ('ifan_name', '%is' % IFNAMSIZ),
              ('ifan_what', 'H'))

    def decode(self):
        bsdmsg.decode(self)
        self['ifan_name'] = self['ifan_name'].strip(b'\0').decode('ascii')
