'''
IPRoute module
==============

`iproute` module provides low-level API to RTNetlink protocol
via `IPRoute` and `IPRSocket` classes as well as all required
constants.

iproute quickstart
------------------

**pyroute2.IPRoute** in two words::

    $ sudo pip install pyroute2
    $ cat >example.py <<EOF
    > from pyroute2 import IPRoute
    > ip = IPRoute()
    > print([x.get_attr('IFLA_IFNAME') for x in ip.get_links()])
    > EOF
    $ python example.py
    ['lo', 'p6p1', 'wlan0', 'virbr0', 'virbr0-nic']

threaded vs. threadless architecture
------------------------------------

Please note, that objects of `IPRoute` class implicitly starts
several threads:

* I/O Loop -- main thread that performs all Netlink I/O and clusterization
* Main thread -- thread that reassembles messages and parses them into
  dict-like structures
* Cache thread -- `IPRoute` objects can be connected together, and in
  this case header masquerading should be performed on netlink packets;
  the thread performs masquerade cache expiration

In most cases it should be ok, `IPRoute` uses no daemonic threads and
explicit `release()` call is provided to stop all the threads. Beside
of that, the architecture provides packet buffering.

But if you do not like implicit threads, you can use simplest
threadless RTNetlink interface, `IPRSocket`.

classes
-------
'''

from socket import htons
from socket import AF_INET
from socket import AF_INET6
from socket import AF_UNSPEC
from pyroute2.netlink import Marshal
from pyroute2.netlink import NetlinkSocket
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NLM_F_ATOMIC
from pyroute2.netlink import NLM_F_ROOT
from pyroute2.netlink import NLM_F_REPLACE
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_CREATE
from pyroute2.netlink import NLM_F_EXCL
from pyroute2.netlink.client import Netlink
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.rtnl.tcmsg import tcmsg
from pyroute2.netlink.rtnl.tcmsg import get_htb_parameters
from pyroute2.netlink.rtnl.tcmsg import get_htb_class_parameters
from pyroute2.netlink.rtnl.tcmsg import get_tbf_parameters
from pyroute2.netlink.rtnl.tcmsg import get_sfq_parameters
from pyroute2.netlink.rtnl.tcmsg import get_u32_parameters
from pyroute2.netlink.rtnl.tcmsg import get_netem_parameters
from pyroute2.netlink.rtnl.tcmsg import get_fw_parameters
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

from pyroute2.common import basestring
from pyroute2.common import map_namespace


#  RTnetlink multicast groups
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

# Types of messages
# RTM_BASE = 16
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

TC_H_INGRESS = 0xfffffff1
TC_H_ROOT = 0xffffffff

DEFAULT_TABLE = 254

RTNL_GROUPS = RTNLGRP_IPV4_IFADDR |\
    RTNLGRP_IPV6_IFADDR |\
    RTNLGRP_IPV4_ROUTE |\
    RTNLGRP_IPV6_ROUTE |\
    RTNLGRP_NEIGH |\
    RTNLGRP_LINK |\
    RTNLGRP_TC

rtypes = {'RTN_UNSPEC': 0,
          'RTN_UNICAST': 1,      # Gateway or direct route
          'RTN_LOCAL': 2,        # Accept locally
          'RTN_BROADCAST': 3,    # Accept locally as broadcast
          #                        send as broadcast
          'RTN_ANYCAST': 4,      # Accept locally as broadcast,
          #                        but send as unicast
          'RTN_MULTICAST': 5,    # Multicast route
          'RTN_BLACKHOLE': 6,    # Drop
          'RTN_UNREACHABLE': 7,  # Destination is unreachable
          'RTN_PROHIBIT': 8,     # Administratively prohibited
          'RTN_THROW': 9,        # Not in this table
          'RTN_NAT': 10,         # Translate this address
          'RTN_XRESOLVE': 11}    # Use external resolver

rtprotos = {'RTPROT_UNSPEC': 0,
            'RTPROT_REDIRECT': 1,  # Route installed by ICMP redirects;
            #                        not used by current IPv4
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


def transform_handle(handle):
    if isinstance(handle, basestring):
        (major, minor) = [int(x if x else '0', 16) for x in handle.split(':')]
        handle = (major << 8 * 2) | minor
    return handle


class MarshalRtnl(Marshal):
    msg_map = {RTM_NEWLINK: ifinfmsg,
               RTM_DELLINK: ifinfmsg,
               RTM_NEWADDR: ifaddrmsg,
               RTM_DELADDR: ifaddrmsg,
               RTM_NEWROUTE: rtmsg,
               RTM_DELROUTE: rtmsg,
               RTM_NEWRULE: rtmsg,
               RTM_DELRULE: rtmsg,
               RTM_NEWNEIGH: ndmsg,
               RTM_DELNEIGH: ndmsg,
               RTM_NEWQDISC: tcmsg,
               RTM_DELQDISC: tcmsg,
               RTM_NEWTCLASS: tcmsg,
               RTM_DELTCLASS: tcmsg,
               RTM_NEWTFILTER: tcmsg,
               RTM_DELTFILTER: tcmsg}

    def fix_message(self, msg):
        # FIXME: pls do something with it
        try:
            msg['event'] = RTM_VALUES[msg['header']['type']]
        except:
            pass


class IPRSocket(NetlinkSocket):
    '''
    The simplest class, that connects together the netlink parser and
    a generic Python socket implementation. Provides method get() to
    receive the next message from netlink socket and parse it. It is
    just simple socket-like class, it implements no buffering or
    like that. It spawns no additional threads, leaving this up to
    developers.

    Please note, that netlink is an asynchronous protocol with
    non-guaranteed delivery. You should be fast enough to get all the
    messages in time. If the message flow rate is higher than the
    speed you parse them with, exceeding messages will be dropped.

    *Usage*

    Threadless RT netlink monitoring with blocking I/O calls:

        >>> from pyroute2.netlink.iproute import IPRSocket
        >>> from pprint import pprint
        >>> s = IPRSocket()
        >>> s.bind()
        >>> pprint(s.get())
        [{'attrs': [('RTA_TABLE', 254),
                    ('RTA_DST', '2a00:1450:4009:808::1002'),
                    ('RTA_GATEWAY', 'fe80:52:0:2282::1fe'),
                    ('RTA_OIF', 2),
                    ('RTA_PRIORITY', 0),
                    ('RTA_CACHEINFO', {'rta_clntref': 0,
                                       'rta_error': 0,
                                       'rta_expires': 0,
                                       'rta_id': 0,
                                       'rta_lastuse': 5926,
                                       'rta_ts': 0,
                                       'rta_tsage': 0,
                                       'rta_used': 1})],
          'dst_len': 128,
          'event': 'RTM_DELROUTE',
          'family': 10,
          'flags': 512,
          'header': {'error': None,
                     'flags': 0,
                     'length': 128,
                     'pid': 0,
                     'sequence_number': 0,
                     'type': 25},
          'proto': 9,
          'scope': 0,
          'src_len': 0,
          'table': 254,
          'tos': 0,
          'type': 1}]
        >>>
    '''

    def __init__(self):
        NetlinkSocket.__init__(self, NETLINK_ROUTE)
        self.marshal = MarshalRtnl()

    def bind(self, groups=RTNL_GROUPS):
        '''
        It is required to call *IPRSocket.bind()* after creation.
        The call subscribes the NetlinkSocket to default RTNL
        groups (`RTNL_GROUPS`) or to a requested group set.
        '''
        NetlinkSocket.bind(self, groups)


class IPRoute(Netlink):
    '''
    You can think of this class in some way as of plain old iproute2
    utility.

    It is an old-style library, that provides access to rtnetlink as is.
    It helps you to retrieve and change almost all the data, available
    through rtnetlink::

        from pyroute2 import IPRoute
        ipr = IPRoute()
            # lookup interface by name
        dev = ipr.link_lookup(ifname='tap0')[0]
            # bring it down
        ipr.link('set', dev, state='down')
            # change interface MAC address and rename it
        ipr.link('set', dev, address='00:11:22:33:44:55', ifname='vpn')
            # add primary IP address
        ipr.addr('add', dev, address='10.0.0.1', mask=24)
            # add secondary IP address
        ipr.addr('add', dev, address='10.0.0.2', mask=24)
            # bring it up
        ipr.link('set', dev, state='up')

    *Usage*

    IPRoute objects allows not only simple monitoring or querying
    of RT netlink, but also clusterization of IPRoute instances.
    Simple local sample:

        >>> from pyroute2 import IPRoute
        >>> from pprint import pprint
        >>> ip = IPRoute()
        >>> ip.monitor()
        >>> pprint(ip.get())
        [{'attrs': [('RTA_TABLE', 255),
                    ('RTA_DST', 'ff02::1:2'),
                    ('RTA_OIF', 3),
                    ('RTA_PRIORITY', 0),
                    ('RTA_CACHEINFO', {'rta_clntref': 1,
                                       'rta_error': 0,
                                       'rta_expires': 0,
                                       'rta_id': 0,
                                       'rta_lastuse': 0,
                                       'rta_ts': 0,
                                       'rta_tsage': 0,
                                       'rta_used': 0})],
          'dst_len': 128,
          'event': 'RTM_NEWROUTE',
          'family': 10,
          'flags': 512,
          'header': {'error': None,
                     'flags': 0,
                     'host': 'netlink://16',
                     'length': 108,
                     'pid': 0,
                     'sequence_number': 0,
                     'type': 24},
          'proto': 0,
          'scope': 0,
          'src_len': 0,
          'table': 255,
          'tos': 0,
          'type': 1}]
        >>>

    IPRoute objects have many methods to get the information
    about Linux network objects:

        >>> pprint(ip.get_routes()[0])
        {'attrs': [('RTA_TABLE', 254),
                   ('RTA_GATEWAY', '10.34.131.254'),
                   ('RTA_OIF', 2)],
         'dst_len': 0,
         'event': 'RTM_NEWROUTE',
         'family': 2,
         'flags': 0,
         'proto': 4,
         'scope': 0,
         'src_len': 0,
         'table': 254,
         'tos': 0,
         'type': 1}
        >>> pprint(ip.get_neighbors()[0])
        {'attrs': [('NDA_DST', 'ff02::2'),
                   ('NDA_LLADDR', '33:33:00:00:00:02'),
                   ('NDA_PROBES', 0),
                   ('NDA_CACHEINFO', {'ndm_confirmed': 309550224,
                                      'ndm_refcnt': 0,
                                      'ndm_updated': 309544224,
                                      'ndm_used': 309544224})],
         'event': 'RTM_NEWNEIGH',
         'family': 10,
         'flags': 0,
         'ifindex': 33554432,
         'ndm_type': 64,
         'state': 0}
        >>>

    But IPRoute objects start additional threads to implement
    transparent authentication, message reassembling and so on.
    Sometimes it can become an overkill for simple projects, in
    these cases consider usage of IPRSocket.
    '''
    marshal = MarshalRtnl
    family = NETLINK_ROUTE
    groups = RTNL_GROUPS

    # 8<---------------------------------------------------------------
    #
    # Listing methods
    #
    def get_qdiscs(self, index=None):
        '''
        Get all queue disciplines for all interfaces or for specified
        one.
        '''
        msg = tcmsg()
        msg['family'] = AF_UNSPEC
        ret = self.nlm_request(msg, RTM_GETQDISC)
        if index is None:
            return ret
        else:
            return [x for x in ret if x['index'] == index]

    def get_filters(self, index=0, handle=0, parent=0):
        '''
        Get filters for specified interface, handle and parent.
        '''
        msg = tcmsg()
        msg['family'] = AF_UNSPEC
        msg['index'] = index
        msg['handle'] = handle
        msg['parent'] = parent
        return self.nlm_request(msg, RTM_GETTFILTER)

    def get_classes(self, index=0):
        '''
        Get classes for specified interface.
        '''
        msg = tcmsg()
        msg['family'] = AF_UNSPEC
        msg['index'] = index
        return self.nlm_request(msg, RTM_GETTCLASS)

    def get_links(self, *argv, **kwarg):
        '''
        Get network interfaces.

        By default returns all interfaces. Arguments vector
        can contain interface indices or a special keyword
        'all'::

            ip.get_links()
            ip.get_links('all')
            ip.get_links(1, 2, 3)

            interfaces = [1, 2, 3]
            ip.get_links(*interfaces)
        '''
        result = []
        links = argv or ['all']
        msg_flags = NLM_F_REQUEST | NLM_F_DUMP
        for index in links:
            msg = ifinfmsg()
            msg['family'] = kwarg.get('family', AF_UNSPEC)
            if index != 'all':
                msg['index'] = index
                msg_flags = NLM_F_REQUEST
            result.extend(self.nlm_request(msg, RTM_GETLINK, msg_flags))
        return result

    def get_neighbors(self, family=AF_UNSPEC):
        '''
        Retrieve ARP cache records.
        '''
        msg = ndmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETNEIGH)

    def get_addr(self, family=AF_UNSPEC):
        '''
        Get all addresses.
        '''
        msg = ifaddrmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETADDR)

    def get_rules(self, family=AF_UNSPEC):
        '''
        Get all rules.
        You can specify inet family, by default return rules for all families.

        Example::
            ip.get_rules() # get all the rules for all families
            ip.get_routes(family=AF_INET6)  # get only IPv6 rules
        '''
        msg = ndmsg()
        msg['family'] = family
        msg_flags = NLM_F_REQUEST | NLM_F_ROOT | NLM_F_ATOMIC
        return self.nlm_request(msg, RTM_GETRULE, msg_flags)

    def get_routes(self, family=AF_UNSPEC, **kwarg):
        '''
        Get all routes. You can specify the table. There
        are 255 routing classes (tables), and the kernel
        returns all the routes on each request. So the
        routine filters routes from full output.

        Example::

            ip.get_routes()  # get all the routes for all families
            ip.get_routes(family=AF_INET6)  # get only IPv6 routes
            ip.get_routes(table=254)  # get routes from 254 table
        '''

        msg_flags = NLM_F_DUMP | NLM_F_REQUEST
        msg = rtmsg()
        msg['family'] = family
        # you can specify the table here, but the kernel
        # will ignore this setting
        table = kwarg.get('table', DEFAULT_TABLE)
        msg['table'] = table if table <= 255 else 252

        # get a particular route
        if kwarg.get('dst', None) is not None:
            dlen = 32 if family == AF_INET else \
                128 if family == AF_INET6 else 0
            msg_flags = NLM_F_REQUEST
            msg['dst_len'] = kwarg.get('dst_len', dlen)

        for key in kwarg:
            nla = rtmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        routes = self.nlm_request(msg, RTM_GETROUTE, msg_flags)
        return [x for x in routes
                if x.get_attr('RTA_TABLE') == table or
                kwarg.get('table', None) is None]
    # 8<---------------------------------------------------------------

    # 8<---------------------------------------------------------------
    #
    # Shortcuts
    #
    # addr_add(), addr_del(), route_add(), route_del() shortcuts are
    # removed due to redundancy. Only link shortcuts are left here for
    # now. Possibly, they should be moved to a separate module.
    #
    def get_default_routes(self, family=AF_UNSPEC, table=DEFAULT_TABLE):
        '''
        Get default routes
        '''
        # according to iproute2/ip/iproute.c:print_route()
        return [x for x in self.get_routes(family, table=table)
                if (x.get_attr('RTA_DST', None) is None and
                    x['dst_len'] == 0)]

    def link_up(self, index):
        '''
        Switch an interface up unconditionally.
        '''
        self.link('set', index=index, state='up')

    def link_down(self, index):
        '''
        Switch an interface down unconditilnally.
        '''
        self.link('set', index=index, state='down')

    def link_rename(self, index, name):
        '''
        Rename an interface. Please note, that the interface must be
        in the `DOWN` state in order to be renamed, otherwise you
        will get an error.
        '''
        self.link('set', index=index, ifname=name)

    def link_remove(self, index):
        '''
        Remove an interface
        '''
        self.link('delete', index=index)

    def link_lookup(self, **kwarg):
        '''
        Lookup interface index (indeces) by first level NLA
        value.

        Example::

            ip.link_lookup(address="52:54:00:9d:4e:3d")
            ip.link_lookup(ifname="lo")
            ip.link_lookup(operstate="UP")

        Please note, that link_lookup() returns list, not one
        value.
        '''
        name = tuple(kwarg.keys())[0]
        value = kwarg[name]

        name = str(name).upper()
        if not name.startswith('IFLA_'):
            name = 'IFLA_%s' % (name)

        return [k['index'] for k in
                [i for i in self.get_links() if 'attrs' in i] if
                [l for l in k['attrs'] if l[0] == name and l[1] == value]]

    def flush_routes(self, *argv, **kwarg):
        '''
        Flush routes -- purge route records from a table.
        Arguments are the same as for `get_routes()`
        routine. Actually, this routine implements a pipe from
        `get_routes()` to `nlm_request()`.
        '''
        flags = NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL | NLM_F_REQUEST
        ret = []
        debug = self.debug
        self.debug = True
        kwarg['table'] = kwarg.get('table', DEFAULT_TABLE)
        for route in self.get_routes(*argv, **kwarg):
            ret.append(self.nlm_request(route,
                                        msg_type=RTM_DELROUTE,
                                        msg_flags=flags))
        self.debug = debug
        return ret
    # 8<---------------------------------------------------------------

    # 8<---------------------------------------------------------------
    #
    # General low-level configuration methods
    #
    def link(self, command, **kwarg):
        '''
        Link operations.

        * command -- set, add or delete
        * index -- device index
        * \*\*kwarg -- keywords, NLA

        Example::

            x = 62  # interface index
            ip.link("set", index=x, state="down")
            ip.link("set", index=x, address="00:11:22:33:44:55", name="bala")
            ip.link("set", index=x, mtu=1000, txqlen=2000)
            ip.link("set", index=x, state="up")

        Keywords "state", "flags" and "mask" are reserved. State can
        be "up" or "down", it is a shortcut::

            state="up":   flags=1, mask=1
            state="down": flags=0, mask=0

        For more flags grep IFF in the kernel code, until we write
        human-readable flag resolver.

        Other keywords are from ifinfmsg.nla_map, look into the
        corresponding module. You can use the form "ifname" as well
        as "IFLA_IFNAME" and so on, so that's equal::

            ip.link("set", index=x, mtu=1000)
            ip.link("set", index=x, IFLA_MTU=1000)

        You can also delete interface with::

            ip.link("delete", index=x)
        '''

        commands = {'set': RTM_SETLINK,      # almost all operations
                    'add': RTM_NEWLINK,      # no idea, how to use it :)
                    'delete': RTM_DELLINK}   # remove interface
        command = commands.get(command, command)

        msg_flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = ifinfmsg()
        # index is required
        msg['index'] = kwarg.get('index')

        flags = kwarg.pop('flags', 0) or 0
        mask = kwarg.pop('mask', 0) or kwarg.pop('change', 0) or 0

        if 'state' in kwarg:
            mask = 1                  # IFF_UP mask
            if kwarg['state'].lower() == 'up':
                flags = 1             # 0 (down) or 1 (up)
            del kwarg['state']

        msg['flags'] = flags
        msg['change'] = mask

        for key in kwarg:
            nla = ifinfmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        return self.nlm_request(msg, msg_type=command, msg_flags=msg_flags)

    def addr(self, command, index, address, mask=24, family=None, scope=0):
        '''
        Address operations

        * command -- add, delete
        * index -- device index
        * address -- IPv4 or IPv6 address
        * mask -- address mask
        * family -- socket.AF_INET for IPv4 or socket.AF_INET6 for IPv6
        * scope -- the address scope, see /etc/iproute2/rt_scopes

        Example::

            index = 62
            ip.addr("add", index, address="10.0.0.1", mask=24)
            ip.addr("add", index, address="10.0.0.2", mask=24)
        '''

        commands = {'add': RTM_NEWADDR,
                    'delete': RTM_DELADDR}
        command = commands.get(command, command)

        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL

        # try to guess family, if it is not forced
        if family is None and address.find(":") > -1:
            family = AF_INET6
        else:
            family = AF_INET

        msg = ifaddrmsg()
        msg['index'] = index
        msg['family'] = family
        msg['prefixlen'] = mask
        msg['scope'] = scope
        if family == AF_INET:
            msg['attrs'] = [['IFA_LOCAL', address],
                            ['IFA_ADDRESS', address]]
        elif family == AF_INET6:
            msg['attrs'] = [['IFA_ADDRESS', address]]
        terminate = lambda x: x['header']['type'] == NLMSG_ERROR
        return self.nlm_request(msg,
                                msg_type=command,
                                msg_flags=flags,
                                terminate=terminate)

    def tc(self, command, kind, index, handle=0, **kwarg):
        '''
        "Swiss knife" for traffic control. With the method you can
        add, delete or modify qdiscs, classes and filters.

        * command -- add or delete qdisc, class, filter.
        * kind -- a string identifier -- "sfq", "htb", "u32" and so on.
        * handle -- integer or string

        Command can be one of ("add", "del", "add-class", "del-class",
        "add-filter", "del-filter") (see `commands` dict in the code).

        Handle notice: traditional iproute2 notation, like "1:0", actually
        represents two parts in one four-bytes integer::

            1:0    ->    0x10000
            1:1    ->    0x10001
            ff:0   ->   0xff0000
            ffff:1 -> 0xffff0001

        For pyroute2 tc() you can use both forms: integer like 0xffff0000
        or string like 'ffff:0000'. By default, handle is 0, so you can add
        simple classless queues w/o need to specify handle. Ingress queue
        causes handle to be 0xffff0000.

        So, to set up sfq queue on interface 1, the function call
        will be like that::

            ip = IPRoute()
            ip.tc("add", "sfq", 1)

        Instead of string commands ("add", "del"...), you can use also
        module constants, `RTM_NEWQDISC`, `RTM_DELQDISC` and so on::

            ip = IPRoute()
            ip.tc(RTM_NEWQDISC, "sfq", 1)

        More complex example with htb qdisc, lets assume eth0 == 2::

            #          u32 -->    +--> htb 1:10 --> sfq 10:0
            #          |          |
            #          |          |
            # eth0 -- htb 1:0 -- htb 1:1
            #          |          |
            #          |          |
            #          u32 -->    +--> htb 1:20 --> sfq 20:0

            eth0 = 2
            # add root queue 1:0
            ip.tc("add", "htb", eth0, 0x10000, default=0x200000)

            # root class 1:1
            ip.tc("add-class", "htb", eth0, 0x10001,
                  parent=0x10000,
                  rate="256kbit",
                  burst=1024 * 6)

            # two branches: 1:10 and 1:20
            ip.tc("add-class", "htb", eth0, 0x10010,
                  parent=0x10001,
                  rate="192kbit",
                  burst=1024 * 6,
                  prio=1)
            ip.tc("add-class", "htb", eht0, 0x10020,
                  parent=0x10001,
                  rate="128kbit",
                  burst=1024 * 6,
                  prio=2)

            # two leaves: 10:0 and 20:0
            ip.tc("add", "sfq", eth0, 0x100000,
                  parent=0x10010,
                  perturb=10)
            ip.tc("add", "sfq", eth0, 0x200000,
                  parent=0x10020,
                  perturb=10)

            # two filters: one to load packets into 1:10 and the
            # second to 1:20
            ip.tc("add-filter", "u32", eth0,
                  parent=0x10000,
                  prio=10,
                  protocol=socket.AF_INET,
                  target=0x10010,
                  keys=["0x0006/0x00ff+8", "0x0000/0xffc0+2"])
            ip.tc("add-filter", "u32", eth0,
                  parent=0x10000,
                  prio=10,
                  protocol=socket.AF_INET,
                  target=0x10020,
                  keys=["0x5/0xf+0", "0x10/0xff+33"])
        '''

        commands = {'add': RTM_NEWQDISC,
                    'del': RTM_DELQDISC,
                    'delete': RTM_DELQDISC,
                    'add-class': RTM_NEWTCLASS,
                    'del-class': RTM_DELTCLASS,
                    'add-filter': RTM_NEWTFILTER,
                    'del-filter': RTM_DELTFILTER}
        command = commands.get(command, command)
        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = tcmsg()
        # transform handle, parent and target, if needed:
        handle = transform_handle(handle)
        for item in ('parent', 'target', 'default'):
            if item in kwarg and kwarg[item] is not None:
                kwarg[item] = transform_handle(kwarg[item])
        msg['index'] = index
        msg['handle'] = handle
        opts = kwarg.get('opts', None)
        if kind == 'ingress':
            msg['parent'] = TC_H_INGRESS
            msg['handle'] = 0xffff0000
        elif kind == 'tbf':
            msg['parent'] = TC_H_ROOT
            if kwarg:
                opts = get_tbf_parameters(kwarg)
        elif kind == 'htb':
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)
            if kwarg:
                if command in (RTM_NEWQDISC, RTM_DELQDISC):
                    opts = get_htb_parameters(kwarg)
                elif command in (RTM_NEWTCLASS, RTM_DELTCLASS):
                    opts = get_htb_class_parameters(kwarg)
        elif kind == 'netem':
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)
            if kwarg:
                opts = get_netem_parameters(kwarg)
        elif kind == 'sfq':
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)
            if kwarg:
                opts = get_sfq_parameters(kwarg)
        elif kind == 'u32':
            msg['parent'] = kwarg.get('parent')
            msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
                ((kwarg.get('prio', 0) << 16) & 0xffff0000)
            if kwarg:
                opts = get_u32_parameters(kwarg)
        elif kind == 'fw':
            msg['parent'] = kwarg.get('parent')
            msg['info'] = htons(kwarg.get('protocol', 0) & 0xffff) |\
                ((kwarg.get('prio', 0) << 16) & 0xffff0000)
            if kwarg:
                opts = get_fw_parameters(kwarg)
        else:
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)

        if kind is not None:
            msg['attrs'] = [['TCA_KIND', kind]]
        if opts is not None:
            msg['attrs'].append(['TCA_OPTIONS', opts])
        return self.nlm_request(msg, msg_type=command, msg_flags=flags)

    def route(self, command,
              rtype='RTN_UNICAST',
              rtproto='RTPROT_STATIC',
              rtscope='RT_SCOPE_UNIVERSE',
              **kwarg):
        '''
        Route operations

        * command -- add, delete
        * prefix -- route prefix
        * mask -- route prefix mask
        * rtype -- route type (default: "RTN_UNICAST")
        * rtproto -- routing protocol (default: "RTPROT_STATIC")
        * rtscope -- routing scope (default: "RT_SCOPE_UNIVERSE")
        * index -- via device index
        * family -- socket.AF_INET (default) or socket.AF_INET6

        `pyroute2/netlink/rtnl/rtmsg.py` rtmsg.nla_map:

        * table -- routing table to use (default: 254)
        * gateway -- via address
        * prefsrc -- preferred source IP address

        etc.

        Example::

            ip.route("add", dst="10.0.0.0", mask=24, gateway="192.168.0.1")
        '''

        # 8<----------------------------------------------------
        # FIXME
        # flags should be moved to some more general place
        flags_base = NLM_F_REQUEST | NLM_F_ACK
        flags_make = flags_base | NLM_F_CREATE | NLM_F_EXCL
        flags_replace = flags_base | NLM_F_REPLACE
        # 8<----------------------------------------------------
        commands = {'add': (RTM_NEWROUTE, flags_make),
                    'set': (RTM_NEWROUTE, flags_replace),
                    'delete': (RTM_DELROUTE, flags_make)}
        (command, flags) = commands.get(command, command)
        msg = rtmsg()
        # table is mandatory; by default == 254
        # if table is not defined in kwarg, save it there
        # also for nla_attr:
        table = kwarg.get('table', 254)
        msg['table'] = table if table <= 255 else 252
        msg['family'] = kwarg.get('family', AF_INET)
        msg['proto'] = rtprotos[rtproto]
        msg['type'] = rtypes[rtype]
        msg['scope'] = rtscopes[rtscope]
        msg['dst_len'] = kwarg.get('dst_len', None) or \
            kwarg.get('mask', 0)
        msg['attrs'] = []
        # FIXME
        # deprecated "prefix" support:
        if 'prefix' in kwarg:
            kwarg['dst'] = kwarg['prefix']

        for key in kwarg:
            nla = rtmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        return self.nlm_request(msg, msg_type=command,
                                msg_flags=flags)

    def rule(self, command, table, priority=32000, rtype='RTN_UNICAST',
             rtscope='RT_SCOPE_UNIVERSE', family=AF_INET, src=None,
             src_len=None, dst=None, dst_len=None, fwmark=None):
        '''
        Rule operations

        * command  - add, delete
        * table    - 0 < table id < 253
        * priority - 0 < rule's priority < 32766
        * rtype    - type of rule, default 'RTN_UNICAST'
        * rtscope  - routing scope, default RT_SCOPE_UNIVERSE
                     (RT_SCOPE_UNIVERSE|RT_SCOPE_SITE|\
                      RT_SCOPE_LINK|RT_SCOPE_HOST|RT_SCOPE_NOWHERE)
        * family   - rule's family (socket.AF_INET (default) or
                     socket.AF_INET6)
        * src      - IP source for Source Based (Policy Based) routing's rule
        * dst      - IP for Destination Based (Policy Based) routing's rule
        * src_len  - Mask for Source Based (Policy Based) routing's rule
        * dst_len  - Mask for Destination Based (Policy Based) routing's rule

        Example::
            ip.rule('add', 10, 32000)

        Will create::
            #ip ru sh
            ...
            32000: from all lookup 10
            ....

        Example::
            iproute.rule('add', 11, 32001, 'RTN_UNREACHABLE')

        Will create::
            #ip ru sh
            ...
            32001: from all lookup 11 unreachable
            ....

        Example::
            iproute.rule('add', 14, 32004, src='10.64.75.141')

        Will create::
            #ip ru sh
            ...
            32004: from 10.64.75.141 lookup 14
            ...

        Example::
            iproute.rule('add', 15, 32005, dst='10.64.75.141', dst_len=24)

        Will create::
            #ip ru sh
            ...
            32005: from 10.64.75.141/24 lookup 15
            ...

        Example::
            iproute.rule('add', 15, 32006, dst='10.64.75.141', fwmark=10)

        Will create::
            #ip ru sh
            ...
            32006: from 10.64.75.141 fwmark 0xa lookup 15
            ...
        '''
        if table < 0 or table > 254:
            raise 'unsupported table number'

        commands = {'add': RTM_NEWRULE,
                    'delete': RTM_DELRULE}
        command = commands.get(command, command)

        msg_flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        msg = rtmsg()
        msg['table'] = table
        msg['family'] = family
        msg['type'] = rtypes[rtype]
        msg['scope'] = rtscopes[rtscope]
        msg['attrs'] = [['RTA_TABLE', table]]
        msg['attrs'].append(['RTA_PRIORITY', priority])
        if fwmark is not None:
            msg['attrs'].append(['RTA_PROTOINFO', fwmark])
        addr_len = {AF_INET6: 128, AF_INET:  32}[family]
        if(dst_len is not None and dst_len >= 0 and dst_len <= addr_len):
            msg['dst_len'] = dst_len
        else:
            msg['dst_len'] = 0
        if(src_len is not None and src_len >= 0 and src_len <= addr_len):
            msg['src_len'] = src_len
        else:
            msg['src_len'] = 0
        if src is not None:
            msg['attrs'].append(['RTA_SRC', src])
            if src_len is None:
                msg['src_len'] = addr_len
        if dst is not None:
            msg['attrs'].append(['RTA_DST', dst])
            if dst_len is None:
                msg['dst_len'] = addr_len

        return self.nlm_request(msg, msg_type=command,
                                msg_flags=msg_flags)
    # 8<---------------------------------------------------------------
