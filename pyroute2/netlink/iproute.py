
from socket import AF_INET
from socket import AF_INET6
from socket import AF_UNSPEC
from pyroute2.netlink import netlink
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_CREATE
from pyroute2.netlink import NLM_F_EXCL
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.generic import marshal
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from pyroute2.common import map_namespace


##  RTnetlink multicast groups
RTNLGRP_NONE = 0x0
RTNLGRP_LINK = 0x1
RTNLGRP_NOTIFY = 0x2
RTNLGRP_NEIGH = 0x4
RTNLGRP_TC = 0x8
RTNLGRP_IPV4_IFADDR = 0x10
RTNLGRP_IPV4_MROUTE = 0x20
RTNLGRP_IPV4_ROUTE = 0x40
RTNLGRP_IPV4_RULE = 0x80
RTNLGRP_IPV6_IFADDR = 0x100
RTNLGRP_IPV6_MROUTE = 0x200
RTNLGRP_IPV6_ROUTE = 0x400
RTNLGRP_IPV6_IFINFO = 0x800
RTNLGRP_DECnet_IFADDR = 0x1000
RTNLGRP_NOP2 = 0x2000
RTNLGRP_DECnet_ROUTE = 0x4000
RTNLGRP_DECnet_RULE = 0x8000
RTNLGRP_NOP4 = 0x10000
RTNLGRP_IPV6_PREFIX = 0x20000
RTNLGRP_IPV6_RULE = 0x40000

## Types of messages
#RTM_BASE = 16
RTM_NEWLINK = 16
RTM_DELLINK = 17
RTM_GETLINK = 18
RTM_SETLINK = 19
RTM_NEWADDR = 20
RTM_DELADDR = 21
RTM_GETADDR = 22
RTM_NEWROUTE = 24
RTM_DELROUTE = 25
RTM_GETROUTE = 26
RTM_NEWNEIGH = 28
RTM_DELNEIGH = 29
RTM_GETNEIGH = 30
RTM_NEWRULE = 32
RTM_DELRULE = 33
RTM_GETRULE = 34
RTM_NEWQDISC = 36
RTM_DELQDISC = 37
RTM_GETQDISC = 38
RTM_NEWTCLASS = 40
RTM_DELTCLASS = 41
RTM_GETTCLASS = 42
RTM_NEWTFILTER = 44
RTM_DELTFILTER = 45
RTM_GETTFILTER = 46
RTM_NEWACTION = 48
RTM_DELACTION = 49
RTM_GETACTION = 50
RTM_NEWPREFIX = 52
RTM_GETMULTICAST = 58
RTM_GETANYCAST = 62
RTM_NEWNEIGHTBL = 64
RTM_GETNEIGHTBL = 66
RTM_SETNEIGHTBL = 67
(RTM_NAMES, RTM_VALUES) = map_namespace('RTM', globals())

rtypes = {'RTN_UNSPEC': 0,
          'RTN_UNICAST': 1,      # Gateway or direct route
          'RTN_LOCAL': 2,        # Accept locally
          'RTN_BROADCAST': 3,    # Accept locally as broadcast
                                 # send as broadcast
          'RTN_ANYCAST': 4,      # Accept locally as broadcast,
                                 # but send as unicast
          'RTN_MULTICAST': 5,    # Multicast route
          'RTN_BLACKHOLE': 6,    # Drop
          'RTN_UNREACHABLE': 7,  # Destination is unreachable
          'RTN_PROHIBIT': 8,     # Administratively prohibited
          'RTN_THROW': 9,        # Not in this table
          'RTN_NAT': 10,         # Translate this address
          'RTN_XRESOLVE': 11}    # Use external resolver

rtprotos = {'RTPROT_UNSPEC': 0,
            'RTPROT_REDIRECT': 1,  # Route installed by ICMP redirects;
                                   # not used by current IPv4
            'RTPROT_KERNEL': 2,    # Route installed by kernel
            'RTPROT_BOOT': 3,      # Route installed during boot
            'RTPROT_STATIC': 4,    # Route installed by administrator
            # Values of protocol >= RTPROT_STATIC are not
            # interpreted by kernel;
            # keep in sync with iproute2 !
            'RTPROT_GATED': 8,      # gated
            'RTPROT_RA': 9,         # RDISC/ND router advertisements
            'RTPROT_MRT': 10,       # Merit MRT
            'RTPROT_ZEBRA': 11,     # Zebra
            'RTPROT_BIRD': 12,      # BIRD
            'RTPROT_DNROUTED': 13,  # DECnet routing daemon
            'RTPROT_XORP': 14,      # XORP
            'RTPROT_NTK': 15,       # Netsukuku
            'RTPROT_DHCP': 16}      # DHCP client

rtscopes = {'RT_SCOPE_UNIVERSE': 0,
            'RT_SCOPE_SITE': 200,
            'RT_SCOPE_LINK': 253,
            'RT_SCOPE_HOST': 254,
            'RT_SCOPE_NOWHERE': 255}


class marshal_rtnl(marshal):
    msg_map = {RTM_NEWLINK: ifinfmsg,
               RTM_DELLINK: ifinfmsg,
               RTM_NEWADDR: ifaddrmsg,
               RTM_DELADDR: ifaddrmsg,
               RTM_NEWROUTE: rtmsg,
               RTM_DELROUTE: rtmsg,
               RTM_NEWNEIGH: ndmsg,
               RTM_DELNEIGH: ndmsg}

    def fix_message(self, msg):
        try:
            msg['event'] = RTM_VALUES[msg['header']['type']]
        except:
            pass


class iproute(netlink):
    marshal = marshal_rtnl
    family = NETLINK_ROUTE
    groups = RTNLGRP_IPV4_IFADDR |\
        RTNLGRP_IPV6_IFADDR |\
        RTNLGRP_IPV4_ROUTE |\
        RTNLGRP_IPV6_ROUTE |\
        RTNLGRP_NEIGH |\
        RTNLGRP_LINK

    # 8<---------------------------------------------------------------
    # listing methods
    #
    def get_all_links(self, family=AF_UNSPEC):
        '''
        Get all network interfaces sepcifications.
        '''
        msg = ifinfmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETLINK)

    def get_all_neighbors(self, family=AF_UNSPEC):
        '''
        Retrieve ARP cache records.
        '''
        msg = ndmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETNEIGH)

    def get_all_addr(self, family=AF_UNSPEC):
        '''
        Get all addresses.
        '''
        msg = ifaddrmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETADDR)

    def get_all_routes(self, family=AF_UNSPEC, table=-1):
        '''
        Get all routes. You can specify the table. There
        are 255 routing classes (tables), and the kernel
        returns all the routes on each request. So the
        routine filters routes from full output. By default,
        table == -1, which means that one should get all
        tables.
        '''
        # moreover, the kernel returns records without
        # RTA_DST, which I don't know how to interpret :)

        msg = rtmsg()
        msg['family'] = family
        # msg['table'] = table  # you can specify the table
                                # here, but the kernel will
                                # ignore this setting
        routes = self.nlm_request(msg, RTM_GETROUTE)
        return [k for k in [i for i in routes if 'attrs' in i]
                if [l for l in k['attrs'] if l[0] == 'RTA_DST'] and
                (k['table'] == table or table == -1)]
    # 8<---------------------------------------------------------------

    # 8<---------------------------------------------------------------
    # add/delete methods
    #
    def add_addr(self, interface, address, mask=24, family=AF_INET):
        '''
        Add an address to an interface.
        '''
        return self._del_add_addr(interface, address, mask, family,
                                  operation=RTM_NEWADDR)

    def del_addr(self, interface, address, mask=24, family=AF_INET):
        '''
        Remove an address from an interface.
        '''
        return self._del_add_addr(interface, address, mask, family,
                                  operation=RTM_DELADDR)

    def add_route(self, prefix, mask, table=254, rtype='RTN_UNICAST',
                  rtproto='RTPROT_STATIC', rtscope='RT_SCOPE_UNIVERSE',
                  interface=None, gateway=None,
                  family=AF_INET):
        '''
        Create a route.
        '''
        return self._del_add_route(prefix, mask, table, rtype, rtproto,
                                   rtscope, interface, gateway, family,
                                   operation=RTM_NEWROUTE)

    def del_route(self, prefix, mask, table=254, rtype='RTN_UNICAST',
                  rtproto='RTPROT_STATIC', rtscope='RT_SCOPE_UNIVERSE',
                  interface=None, gateway=None,
                  family=AF_INET):
        '''
        Delete a route.
        '''
        return self._del_add_route(prefix, mask, table, rtype, rtproto,
                                   rtscope, interface, gateway, family,
                                   operation=RTM_DELROUTE)
    # 8<---------------------------------------------------------------

    # 8<---------------------------------------------------------------
    # private methods
    #
    def _del_add_addr(self, interface, address, mask=24, family=AF_INET,
                      operation=RTM_NEWADDR):
        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = ifaddrmsg()
        msg['index'] = interface
        msg['family'] = family
        msg['prefixlen'] = mask
        msg['scope'] = 0xfe
        if family == AF_INET:
            msg['attrs'] = (('IFA_LOCAL', address),
                            ('IFA_ADDRESS', address))
        elif family == AF_INET6:
            msg['attrs'] = (('IFA_ADDRESS', address), )
        return self.nlm_request(msg, msg_type=operation, msg_flags=flags)

    def _del_add_route(self, prefix, mask,
                       table=254, rtype='RTN_UNICAST',
                       rtproto='RTPROT_STATIC', rtscope='RT_SCOPE_UNIVERSE',
                       interface=None, gateway=None,
                       family=AF_INET, operation=RTM_NEWROUTE):

        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = rtmsg()
        msg['table'] = table
        msg['family'] = family
        msg['proto'] = rtprotos[rtproto]
        msg['type'] = rtypes[rtype]
        msg['scope'] = rtscopes[rtscope]
        msg['dst_len'] = mask
        msg['attrs'] = [('RTA_DST', prefix),
                        ('RTA_TABLE', table)]
        if interface is not None:
            msg['attrs'].append(('RTA_OIF', interface))
        if gateway is not None:
            msg['attrs'].append(('RTA_GATEWAY', gateway))

        return self.nlm_request(msg, msg_type=operation,
                                msg_flags=flags)
    # 8<---------------------------------------------------------------
