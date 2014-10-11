from pyroute2.common import map_namespace
from pyroute2.netlink import nla
from pyroute2.netlink import nlmsg
from pyroute2.netlink.rtnl.iw_event import iw_event

IFF_UP = 0x1  # interface is up
IFF_BROADCAST = 0x2  # broadcast address valid
IFF_DEBUG = 0x4  # turn on debugging
IFF_LOOPBACK = 0x8  # is a loopback net
IFF_POINTOPOINT = 0x10  # interface is has p-p link
IFF_NOTRAILERS = 0x20  # avoid use of trailers
IFF_RUNNING = 0x40  # interface RFC2863 OPER_UP
IFF_NOARP = 0x80  # no ARP protocol
IFF_PROMISC = 0x100  # receive all packets
IFF_ALLMULTI = 0x200  # receive all multicast packets
IFF_MASTER = 0x400  # master of a load balancer
IFF_SLAVE = 0x800  # slave of a load balancer
IFF_MULTICAST = 0x1000  # Supports multicast
IFF_PORTSEL = 0x2000  # can set media type
IFF_AUTOMEDIA = 0x4000  # auto media select active
IFF_DYNAMIC = 0x8000  # dialup device with changing addresses
IFF_LOWER_UP = 0x10000  # driver signals L1 up
IFF_DORMANT = 0x20000  # driver signals dormant
IFF_ECHO = 0x40000  # echo sent packets

IFF_MASK = IFF_UP |\
    IFF_DEBUG |\
    IFF_NOTRAILERS |\
    IFF_NOARP |\
    IFF_PROMISC |\
    IFF_ALLMULTI

IFF_VOLATILE = IFF_LOOPBACK |\
    IFF_POINTOPOINT |\
    IFF_BROADCAST |\
    IFF_ECHO |\
    IFF_MASTER |\
    IFF_SLAVE |\
    IFF_RUNNING |\
    IFF_LOWER_UP |\
    IFF_DORMANT

(IFF_NAMES, IFF_VALUES) = map_namespace('IFF', globals())

states = ('UNKNOWN',
          'NOTPRESENT',
          'DOWN',
          'LOWERLAYERDOWN',
          'TESTING',
          'DORMANT',
          'UP')
state_by_name = dict(((i[1], i[0]) for i in enumerate(states)))
state_by_code = dict(enumerate(states))
stats_names = ('rx_packets',
               'tx_packets',
               'rx_bytes',
               'tx_bytes',
               'rx_errors',
               'tx_errors',
               'rx_dropped',
               'tx_dropped',
               'multicast',
               'collisions',
               'rx_length_errors',
               'rx_over_errors',
               'rx_crc_errors',
               'rx_frame_errors',
               'rx_fifo_errors',
               'rx_missed_errors',
               'tx_aborted_errors',
               'tx_carrier_errors',
               'tx_fifo_errors',
               'tx_heartbeat_errors',
               'tx_window_errors',
               'rx_compressed',
               'tx_compressed')


class ifinfmsg(nlmsg):
    '''
    Network interface message
    struct ifinfomsg {
        unsigned char  ifi_family; /* AF_UNSPEC */
        unsigned short ifi_type;   /* Device type */
        int            ifi_index;  /* Interface index */
        unsigned int   ifi_flags;  /* Device flags  */
        unsigned int   ifi_change; /* change mask */
    };
    '''
    prefix = 'IFLA_'

    fields = (('family', 'B'),
              ('__align', 'B'),
              ('ifi_type', 'H'),
              ('index', 'i'),
              ('flags', 'I'),
              ('change', 'I'))

    nla_map = (('IFLA_UNSPEC', 'none'),
               ('IFLA_ADDRESS', 'l2addr'),
               ('IFLA_BROADCAST', 'l2addr'),
               ('IFLA_IFNAME', 'asciiz'),
               ('IFLA_MTU', 'uint32'),
               ('IFLA_LINK', 'uint32'),
               ('IFLA_QDISC', 'asciiz'),
               ('IFLA_STATS', 'ifstats'),
               ('IFLA_COST', 'hex'),
               ('IFLA_PRIORITY', 'hex'),
               ('IFLA_MASTER', 'uint32'),
               ('IFLA_WIRELESS', 'wireless'),
               ('IFLA_PROTINFO', 'hex'),
               ('IFLA_TXQLEN', 'uint32'),
               ('IFLA_MAP', 'ifmap'),
               ('IFLA_WEIGHT', 'hex'),
               ('IFLA_OPERSTATE', 'state'),
               ('IFLA_LINKMODE', 'uint8'),
               ('IFLA_LINKINFO', 'ifinfo'),
               ('IFLA_NET_NS_PID', 'hex'),
               ('IFLA_IFALIAS', 'hex'),
               ('IFLA_NUM_VF', 'uint32'),
               ('IFLA_VFINFO_LIST', 'hex'),
               ('IFLA_STATS64', 'ifstats64'),
               ('IFLA_VF_PORTS', 'hex'),
               ('IFLA_PORT_SELF', 'hex'),
               ('IFLA_AF_SPEC', 'af_spec'),
               ('IFLA_GROUP', 'uint32'),
               ('IFLA_NET_NS_FD', 'hex'),
               ('IFLA_EXT_MASK', 'hex'),
               ('IFLA_PROMISCUITY', 'uint32'),
               ('IFLA_NUM_TX_QUEUES', 'uint32'),
               ('IFLA_NUM_RX_QUEUES', 'uint32'))

    @staticmethod
    def flags2names(flags):
        ret = []
        for flag in IFF_VALUES:
            if flag & flags:
                ret.append(IFF_VALUES[flag])
        return ret

    @staticmethod
    def names2flags(flags):
        ret = 0
        for flag in flags:
            ret |= IFF_NAMES[flag]
        return ret

    def encode(self):
        # convert flags
        if isinstance(self['flags'], (set, tuple, list)):
            self['flags'] = self.names2flags(self['flags'])
        return nlmsg.encode(self)

    class wireless(iw_event):
        pass

    class state(nla):
        fields = (('value', 'B'), )

        def encode(self):
            self['value'] = state_by_name[self.value]
            nla.encode(self)

        def decode(self):
            nla.decode(self)
            self.value = state_by_code[self['value']]

    class ifstats(nla):
        fields = [(i, 'I') for i in stats_names]

    class ifstats64(nla):
        fields = [(i, 'Q') for i in stats_names]

    class ifmap(nla):
        fields = (('mem_start', 'Q'),
                  ('mem_end', 'Q'),
                  ('base_addr', 'Q'),
                  ('irq', 'H'),
                  ('dma', 'B'),
                  ('port', 'B'))

    class ifinfo(nla):
        nla_map = (('IFLA_INFO_UNSPEC', 'none'),
                   ('IFLA_INFO_KIND', 'asciiz'),
                   ('IFLA_INFO_DATA', 'info_data'),
                   ('IFLA_INFO_XSTATS', 'hex'))

        def info_data(self, *argv, **kwarg):
            '''
            The function returns appropriate IFLA_INFO_DATA
            type according to IFLA_INFO_KIND info. Return
            'hex' type for all unknown kind's and when the
            kind is not known.
            '''
            kind = self.get_attr('IFLA_INFO_KIND')
            if kind == 'vlan':
                return self.vlan_data
            elif kind == 'bond':
                return self.bond_data
            return self.hex

        class vlan_data(nla):
            nla_map = (('IFLA_VLAN_UNSPEC', 'none'),
                       ('IFLA_VLAN_ID', 'uint16'),
                       ('IFLA_VLAN_FLAGS', 'vlan_flags'),
                       ('IFLA_VLAN_EGRESS_QOS', 'hex'),
                       ('IFLA_VLAN_INGRESS_QOS', 'hex'))

            class vlan_flags(nla):
                fields = (('flags', 'I'),
                          ('mask', 'I'))

        class bond_data(nla):
            nla_map = (('IFLA_BOND_UNSPEC', 'none'),
                       ('IFLA_BOND_MODE', 'uint8'),
                       ('IFLA_BOND_ACTIVE_SLAVE', 'uint32'))

    class af_spec(nla):
        nla_map = (('AF_UNSPEC', 'none'),
                   ('AF_UNIX', 'hex'),
                   ('AF_INET', 'inet'),
                   ('AF_AX25', 'hex'),
                   ('AF_IPX', 'hex'),
                   ('AF_APPLETALK', 'hex'),
                   ('AF_NETROM', 'hex'),
                   ('AF_BRIDGE', 'hex'),
                   ('AF_ATMPVC', 'hex'),
                   ('AF_X25', 'hex'),
                   ('AF_INET6', 'inet6'))

        class inet(nla):
            #  ./include/linux/inetdevice.h: struct ipv4_devconf
            field_names = ('sysctl',
                           'forwarding',
                           'mc_forwarding',
                           'proxy_arp',
                           'accept_redirects',
                           'secure_redirects',
                           'send_redirects',
                           'shared_media',
                           'rp_filter',
                           'accept_source_route',
                           'bootp_relay',
                           'log_martians',
                           'tag',
                           'arp_filter',
                           'medium_id',
                           'disable_xfrm',
                           'disable_policy',
                           'force_igmp_version',
                           'arp_announce',
                           'arp_ignore',
                           'promote_secondaries',
                           'arp_accept',
                           'arp_notify',
                           'accept_local',
                           'src_valid_mark',
                           'proxy_arp_pvlan',
                           'route_localnet')
            fields = [(i, 'I') for i in field_names]

        class inet6(nla):
            nla_map = (('IFLA_INET6_UNSPEC', 'none'),
                       ('IFLA_INET6_FLAGS', 'uint32'),
                       ('IFLA_INET6_CONF', 'ipv6_devconf'),
                       ('IFLA_INET6_STATS', 'ipv6_stats'),
                       ('IFLA_INET6_MCAST', 'hex'),
                       ('IFLA_INET6_CACHEINFO', 'ipv6_cache_info'),
                       ('IFLA_INET6_ICMP6STATS', 'icmp6_stats'))

            class ipv6_devconf(nla):
                # ./include/uapi/linux/ipv6.h
                # DEVCONF_
                field_names = ('forwarding',
                               'hop_limit',
                               'mtu',
                               'accept_ra',
                               'accept_redirects',
                               'autoconf',
                               'dad_transmits',
                               'router_solicitations',
                               'router_solicitation_interval',
                               'router_solicitation_delay',
                               'use_tempaddr',
                               'temp_valid_lft',
                               'temp_prefered_lft',
                               'regen_max_retry',
                               'max_desync_factor',
                               'max_addresses',
                               'force_mld_version',
                               'accept_ra_defrtr',
                               'accept_ra_pinfo',
                               'accept_ra_rtr_pref',
                               'router_probe_interval',
                               'accept_ra_rt_info_max_plen',
                               'proxy_ndp',
                               'optimistic_dad',
                               'accept_source_route',
                               'mc_forwarding',
                               'disable_ipv6',
                               'accept_dad',
                               'force_tllao',
                               'ndisc_notify')
                fields = [(i, 'I') for i in field_names]

            class ipv6_cache_info(nla):
                # ./include/uapi/linux/if_link.h: struct ifla_cacheinfo
                fields = (('max_reasm_len', 'I'),
                          ('tstamp', 'I'),
                          ('reachable_time', 'I'),
                          ('retrans_time', 'I'))

            class ipv6_stats(nla):
                field_names = ('inoctets',
                               'fragcreates',
                               'indiscards',
                               'num',
                               'outoctets',
                               'outnoroutes',
                               'inbcastoctets',
                               'outforwdatagrams',
                               'outpkts',
                               'reasmtimeout',
                               'inhdrerrors',
                               'reasmreqds',
                               'fragfails',
                               'outmcastpkts',
                               'inaddrerrors',
                               'inmcastpkts',
                               'reasmfails',
                               'outdiscards',
                               'outbcastoctets',
                               'inmcastoctets',
                               'inpkts',
                               'fragoks',
                               'intoobigerrors',
                               'inunknownprotos',
                               'intruncatedpkts',
                               'outbcastpkts',
                               'reasmoks',
                               'inbcastpkts',
                               'innoroutes',
                               'indelivers',
                               'outmcastoctets')
                fields = [(i, 'I') for i in field_names]

            class icmp6_stats(nla):
                fields = (('num', 'Q'),
                          ('inerrors', 'Q'),
                          ('outmsgs', 'Q'),
                          ('outerrors', 'Q'),
                          ('inmsgs', 'Q'))
