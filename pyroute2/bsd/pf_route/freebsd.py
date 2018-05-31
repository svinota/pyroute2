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


class rt_msg_base(bsdmsg):

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


class ifa_msg_base(bsdmsg):

    __slots__ = ()
    fields = (('rtm_addrs', 'i'),
              ('ifam_flags', 'i'),
              ('ifam_index', 'H'),
              ('ifam_metric', 'i'))
    sockaddr_offset = 20


class ifma_msg_base(bsdmsg):

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
