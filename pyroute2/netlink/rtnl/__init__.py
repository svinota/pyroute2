'''
RTNetlink: network setup
========================

RTNL is a netlink protocol, used to get and set information
about different network objects -- addresses, routes, interfaces
etc.

RTNL protocol-specific data in messages depends on the object
type. E.g., complete packet with the interface address information::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid
    ifaddrmsg structure:
        + unsigned char ifa_family
        + unsigned char ifa_prefixlen
        + unsigned char ifa_flags
        + unsigned char ifa_scope
        + uint32 ifa_index
    [ optional NLA tree ]

NLA for this kind of packets can be of type IFA_ADDRESS, IFA_LOCAL
etc. -- please refer to the corresponding source.

Other objects types require different structures, sometimes really
complex. All these structures are described in sources.

---------------------------

Module contents:

'''

import os
import io
import time
import subprocess
from pyroute2.common import map_namespace
from pyroute2.common import ANCIENT
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NETLINK_ROUTE
from pyroute2.netlink.nlsocket import Marshal
from pyroute2.netlink.nlsocket import NetlinkSocket
from pyroute2.netlink.rtnl.errmsg import errmsg
from pyroute2.netlink.rtnl.tcmsg import tcmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.bomsg import bomsg
from pyroute2.netlink.rtnl.brmsg import brmsg
from pyroute2.netlink.rtnl.dhcpmsg import dhcpmsg
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg


_ANCIENT_BARRIER = 0.3
_BONDING_MASTERS = '/sys/class/net/bonding_masters'
_BONDING_SLAVES = '/sys/class/net/%s/bonding/slaves'
_BRIDGE_MASTER = '/sys/class/net/%s/brport/bridge/ifindex'
_BONDING_MASTER = '/sys/class/net/%s/master/ifindex'

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
# custom message types
RTM_GETBRIDGE = 88
RTM_SETBRIDGE = 89
RTM_GETBOND = 90
RTM_SETBOND = 91
RTM_GETDHCP = 92
RTM_SETDHCP = 93
(RTM_NAMES, RTM_VALUES) = map_namespace('RTM', globals())

TC_H_INGRESS = 0xfffffff1
TC_H_ROOT = 0xffffffff


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


class MarshalRtnl(Marshal):
    msg_map = {RTM_NEWLINK: ifinfmsg,
               RTM_DELLINK: ifinfmsg,
               RTM_GETLINK: ifinfmsg,
               RTM_SETLINK: ifinfmsg,
               RTM_NEWADDR: ifaddrmsg,
               RTM_DELADDR: ifaddrmsg,
               RTM_GETADDR: ifaddrmsg,
               RTM_NEWROUTE: rtmsg,
               RTM_DELROUTE: rtmsg,
               RTM_GETROUTE: rtmsg,
               RTM_NEWRULE: rtmsg,
               RTM_DELRULE: rtmsg,
               RTM_GETRULE: rtmsg,
               RTM_NEWNEIGH: ndmsg,
               RTM_DELNEIGH: ndmsg,
               RTM_GETNEIGH: ndmsg,
               RTM_NEWQDISC: tcmsg,
               RTM_DELQDISC: tcmsg,
               RTM_GETQDISC: tcmsg,
               RTM_NEWTCLASS: tcmsg,
               RTM_DELTCLASS: tcmsg,
               RTM_GETTCLASS: tcmsg,
               RTM_NEWTFILTER: tcmsg,
               RTM_DELTFILTER: tcmsg,
               RTM_GETTFILTER: tcmsg,
               RTM_GETBRIDGE: brmsg,
               RTM_SETBRIDGE: brmsg,
               RTM_GETBOND: bomsg,
               RTM_SETBOND: bomsg,
               RTM_GETDHCP: dhcpmsg,
               RTM_SETDHCP: dhcpmsg}

    def fix_message(self, msg):
        # FIXME: pls do something with it
        try:
            msg['event'] = RTM_VALUES[msg['header']['type']]
        except:
            pass


class IPRSocketMixin(object):
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

        >>> from pyroute2 import IPRSocket
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
        super(IPRSocketMixin, self).__init__(NETLINK_ROUTE)
        self.marshal = MarshalRtnl()
        self.get_map = {RTM_NEWLINK: self.get_newlink}
        self.put_map = {RTM_NEWLINK: self.put_newlink,
                        RTM_SETLINK: self.put_setlink,
                        RTM_DELLINK: self.put_dellink,
                        RTM_SETBRIDGE: self.put_setbr,
                        RTM_GETBRIDGE: self.put_getbr,
                        RTM_SETBOND: self.put_setbo,
                        RTM_GETBOND: self.put_getbo,
                        RTM_SETDHCP: self.put_setdhcp,
                        RTM_GETDHCP: self.put_getdhcp}
        self.ancient = ANCIENT

    def bind(self, groups=RTNL_GROUPS, async=False):
        '''
        It is required to call *IPRSocket.bind()* after creation.
        The call subscribes the NetlinkSocket to default RTNL
        groups (`RTNL_GROUPS`) or to a requested group set.
        '''
        super(IPRSocketMixin, self).bind(groups, async=async)

    def name_by_id(self, index):
        return self.get_links(index)[0].get_attr('IFLA_IFNAME')

    ##
    # proxy protocol
    #
    def get(self, *argv, **kwarg):
        '''
        Proxy `get()` request
        '''
        msgs = super(IPRSocketMixin, self).get(*argv, **kwarg)
        for msg in msgs:
            mtype = msg['header']['type']
            if mtype in self.get_map:
                self.get_map[mtype](msg)
        return msgs

    def put(self, *argv, **kwarg):
        '''
        Proxy `put()` request
        '''
        if argv[1] in self.put_map:
            self.put_map[argv[1]](*argv, **kwarg)
        else:
            super(IPRSocketMixin, self).put(*argv, **kwarg)

    ##
    # proxy hooks
    #
    def put_newlink(self, msg, *argv, **kwarg):
        if self.ancient:
            # get the interface kind
            linkinfo = msg.get_attr('IFLA_LINKINFO')
            if linkinfo is not None:
                kind = [x[1] for x in linkinfo['attrs']
                        if x[0] == 'IFLA_INFO_KIND']
                if kind:
                    kind = kind[0]
                # not covered types, pass to the system
                if kind not in ('bridge', 'bond'):
                    return super(IPRSocketMixin, self).put(msg, *argv, **kwarg)
                ##
                # otherwise, create a valid answer --
                # NLMSG_ERROR with code 0 (no error)
                ##
                # FIXME: intercept and return valid RTM_NEWLINK
                ##
                response = ifinfmsg()
                seq = kwarg.get('msg_seq', 0)
                response['header']['type'] = NLMSG_ERROR
                response['header']['sequence_number'] = seq
                # route the request
                if kind == 'bridge':
                    compat_create_bridge(msg.get_attr('IFLA_IFNAME'))
                elif kind == 'bond':
                    compat_create_bond(msg.get_attr('IFLA_IFNAME'))
                # while RTM_NEWLINK is not intercepted -- sleep
                time.sleep(_ANCIENT_BARRIER)
                response.encode()
                response = response.copy()
                self.backlog[seq] = [response]
        else:
            # else just send the packet
            super(IPRSocketMixin, self).put(msg, *argv, **kwarg)

    def get_newlink(self, msg):
        if self.ancient:
            ifname = msg.get_attr('IFLA_IFNAME')
            # fix master
            master = compat_get_master(ifname)
            if master is not None:
                msg['attrs'].append(['IFLA_MASTER', master])
            # fix linkinfo
            li = msg.get_attr('IFLA_LINKINFO')
            if li is not None:
                kind = li.get_attr('IFLA_INFO_KIND')
                name = msg.get_attr('IFLA_IFNAME')
                if (kind is None) and (name is not None):
                    kind = get_interface_type(kind)
                    li['attrs'].append(['IFLA_INFO_KIND', kind])
            msg.reset()
            msg.encode()
            return msg

    def put_setdhcp(self, msg, *argv, **kwarg):
        pass

    def put_getdhcp(self, msg, *argv, **kwarg):
        address = msg.get_attr('DHCP_ADDRESS')
        name = msg.get_attr('DHCP_IFNAME')

        options = []
        agentinfo = None
        seq = kwarg.get('msg_seq', 0)
        response = dhcpmsg()
        response['header']['type'] = RTM_SETDHCP
        response['header']['sequence_number'] = seq
        response['index'] = msg['index']
        response['family'] = msg['family']
        response['prefixlen'] = msg['prefixlen']

        # so far only dhclient is supported
        # more agents -- issue a feature request

        # take the first running agent on the interface
        # TODO: move all the DHCP stuff to a separate module
        # get the interface name
        buf = io.BytesIO()
        buf.write(subprocess.check_output(['ps', 'ax', '--cols', '4096']))
        buf.seek(0)

        def match_lease(f, name, address):
            lease_match = False
            for lease_line in l.readlines():
                if lease_line.find('interface') > -1:
                    if lease_line.find('"%s"' % name) > -1:
                        lease_match = True
                    else:
                        lease_match = False
                elif lease_line.find('fixed-address') > -1 \
                        and lease_line.find(address) > -1 \
                        and lease_match:
                    return True

        for line in buf.readlines():
            if line.find('/sbin/dhclient') > -1:
                line = line.split()
                if line[-1] != name:
                    continue

                agentinfo = []
                agentinfo.append(['DHCP_AGENT', 'dhclient'])
                agentinfo.append(['DHCP_AGENT_PID', int(line[0])])
                agentinfo.append(['DHCP_AGENT_STATUS', 'running'])

                # that's our dhclient
                if address is None:
                    break

                # match the client
                for field in line:
                    # 1. extract the lease file
                    if field == '-lf':
                        lease = line[line.index(field) + 1]
                        try:
                            with open(lease, 'r') as l:
                                if match_lease(l, name, address):
                                    options.append(['DHCP_ADDRESS', address])
                                    break
                                else:
                                    agentinfo = []
                        except IOError:
                            pass
                else:
                    # 2. default lease file
                    try:
                        lease = '/var/lib/dhclient/dhclient.leases'
                        with open(lease, 'r') as l:
                            if match_lease(l, name, address):
                                options.append(['DHCP_ADDRESS', address])
                            else:
                                agentinfo = []
                    except IOError:
                        pass
                break

        if agentinfo:
            options.append(['DHCP_AGENTINFO', {'attrs': agentinfo}])
            options.append(['DHCP_IFNAME', name])
        response['attrs'] = options
        response.encode()
        response = response.copy()
        self.backlog[seq] = [response]

    def put_getbo(self, msg, *argv, **kwarg):
        t = '/sys/class/net/%s/bonding/%s'
        name = msg.get_attr('IFBO_IFNAME')
        commands = []
        seq = kwarg.get('msg_seq', 0)
        response = bomsg()
        response['header']['type'] = RTM_SETBOND
        response['header']['sequence_number'] = seq
        response['index'] = msg['index']
        response['attrs'] = [['IFBO_COMMANDS', {'attrs': commands}]]
        for cmd, _ in bomsg.commands.nla_map:
            try:
                with open(t % (name, bomsg.nla2name(cmd)), 'r') as f:
                    value = f.read()
                if cmd == 'IFBO_MODE':
                    value = value.split()[1]
                commands.append([cmd, int(value)])
            except:
                pass
        response.encode()
        response = response.copy()
        self.backlog[seq] = [response]

    def put_getbr(self, msg, *argv, **kwarg):
        t = '/sys/class/net/%s/bridge/%s'
        name = msg.get_attr('IFBR_IFNAME')
        commands = []
        seq = kwarg.get('msg_seq', 0)
        response = brmsg()
        response['header']['type'] = RTM_SETBRIDGE
        response['header']['sequence_number'] = seq
        response['index'] = msg['index']
        response['attrs'] = [['IFBR_COMMANDS', {'attrs': commands}]]
        for cmd, _ in brmsg.commands.nla_map:
            try:
                with open(t % (name, brmsg.nla2name(cmd)), 'r') as f:
                    value = f.read()
                commands.append([cmd, int(value)])
            except:
                pass
        response.encode()
        response = response.copy()
        self.backlog[seq] = [response]

    def put_setbo(self, msg, *argv, **kwarg):
        #
        name = msg.get_attr('IFBO_IFNAME')
        code = 0
        #
        for (cmd, value) in msg.get_attr('IFBO_COMMANDS',
                                         {'attrs': []}).get('attrs', []):
            cmd = bomsg.nla2name(cmd)
            code = compat_set_bond(name, cmd, value) or code
        seq = kwarg.get('msg_seq', 0)
        response = errmsg()
        response['header']['type'] = NLMSG_ERROR
        response['header']['sequence_number'] = seq
        response['code'] = code
        response.encode()
        response = response.copy()
        self.backlog[seq] = [response]

    def put_setbr(self, msg, *argv, **kwarg):
        #
        name = msg.get_attr('IFBR_IFNAME')
        code = 0
        # iterate commands:
        for (cmd, value) in msg.get_attr('IFBR_COMMANDS',
                                         {'attrs': []}).get('attrs', []):
            cmd = brmsg.nla2name(cmd)
            code = compat_set_bridge(name, cmd, value) or code

        seq = kwarg.get('msg_seq', 0)
        response = errmsg()
        response['header']['type'] = NLMSG_ERROR
        response['header']['sequence_number'] = seq
        response['code'] = code
        response.encode()
        response = response.copy()
        self.backlog[seq] = [response]

    def put_setlink(self, msg, *argv, **kwarg):
        # is it a port setup?
        master = msg.get_attr('IFLA_MASTER')
        if self.ancient and master is not None:
            seq = kwarg.get('msg_seq', 0)
            response = ifinfmsg()
            response['header']['type'] = NLMSG_ERROR
            response['header']['sequence_number'] = seq
            ifname = self.name_by_id(msg['index'])
            if master == 0:
                # port delete
                # 1. get the current master
                m = self.name_by_id(compat_get_master(ifname))
                # 2. get the type of the master
                kind = compat_get_type(m)
                # 3. delete the port
                if kind == 'bridge':
                    compat_del_bridge_port(m, ifname)
                elif kind == 'bond':
                    compat_del_bond_port(m, ifname)
            else:
                # port add
                # 1. get the name of the master
                m = self.name_by_id(master)
                # 2. get the type of the master
                kind = compat_get_type(m)
                # 3. add the port
                if kind == 'bridge':
                    compat_add_bridge_port(m, ifname)
                elif kind == 'bond':
                    compat_add_bond_port(m, ifname)
            response.encode()
            response = response.copy()
            self.backlog[seq] = [response]
        super(IPRSocketMixin, self).put(msg, *argv, **kwarg)

    def put_dellink(self, msg, *argv, **kwarg):
        if self.ancient:
            # get the interface kind
            kind = compat_get_type(msg.get_attr('IFLA_IFNAME'))

            # not covered types pass to the system
            if kind not in ('bridge', 'bond'):
                return super(IPRSocketMixin, self).put(msg, *argv, **kwarg)
            ##
            # otherwise, create a valid answer --
            # NLMSG_ERROR with code 0 (no error)
            ##
            # FIXME: intercept and return valid RTM_NEWLINK
            ##
            seq = kwarg.get('msg_seq', 0)
            response = ifinfmsg()
            response['header']['type'] = NLMSG_ERROR
            response['header']['sequence_number'] = seq
            # route the request
            if kind == 'bridge':
                compat_del_bridge(msg.get_attr('IFLA_IFNAME'))
            elif kind == 'bond':
                compat_del_bond(msg.get_attr('IFLA_IFNAME'))
            # while RTM_NEWLINK is not intercepted -- sleep
            time.sleep(_ANCIENT_BARRIER)
            response.encode()
            response = response.copy()
            self.backlog[seq] = [response]
        else:
            # else just send the packet
            super(IPRSocketMixin, self).put(msg, *argv, **kwarg)


class IPRSocket(IPRSocketMixin, NetlinkSocket):
    pass


def get_interface_type(name):
    '''
    Utility function to get interface type.

    Unfortunately, we can not rely on RTNL or even ioctl().
    RHEL doesn't support interface type in RTNL and doesn't
    provide extended (private) interface flags via ioctl().

    Args:
        * name (str): interface name

    Returns:
        * False -- sysfs info unavailable
        * None -- type not known
        * str -- interface type:
            * 'bond'
            * 'bridge'
    '''
    # FIXME: support all interface types? Right now it is
    # not needed
    try:
        ifattrs = os.listdir('/sys/class/net/%s/' % (name))
    except OSError as e:
        if e.errno == 2:
            return False
        else:
            raise

    if 'bonding' in ifattrs:
        return 'bond'
    elif 'bridge' in ifattrs:
        return 'bridge'
    else:
        return None


def compat_get_type(name):
    ##
    # is it bridge?
    try:
        with open('/sys/class/net/%s/bridge/stp_state' % name, 'r'):
            return 'bridge'
    except IOError:
        pass
    ##
    # is it bond?
    try:
        with open('/sys/class/net/%s/bonding/mode' % name, 'r'):
            return 'bond'
    except IOError:
        pass
    ##
    # don't care
    return 'unknown'


def compat_set_bond(name, cmd, value):
    # FIXME: join with bridge
    # FIXME: use internal IO, not bash
    t = 'echo %s >/sys/class/net/%s/bonding/%s'
    with open(os.devnull, 'w') as fnull:
        return subprocess.call(['bash', '-c', t % (value, name, cmd)],
                               stdout=fnull,
                               stderr=fnull)


def compat_set_bridge(name, cmd, value):
    t = 'echo %s >/sys/class/net/%s/bridge/%s'
    with open(os.devnull, 'w') as fnull:
        return subprocess.call(['bash', '-c', t % (value, name, cmd)],
                               stdout=fnull,
                               stderr=fnull)


def compat_create_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'addbr', name],
                              stdout=fnull,
                              stderr=fnull)


def compat_create_bond(name):
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('+%s' % (name))


def compat_del_bridge(name):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['ip', 'link', 'set',
                               'dev', name, 'down'])
        subprocess.check_call(['brctl', 'delbr', name],
                              stdout=fnull,
                              stderr=fnull)


def compat_del_bond(name):
    subprocess.check_call(['ip', 'link', 'set',
                           'dev', name, 'down'])
    with open(_BONDING_MASTERS, 'w') as f:
        f.write('-%s' % (name))


def compat_add_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'addif', master, port],
                              stdout=fnull,
                              stderr=fnull)


def compat_del_bridge_port(master, port):
    with open(os.devnull, 'w') as fnull:
        subprocess.check_call(['brctl', 'delif', master, port],
                              stdout=fnull,
                              stderr=fnull)


def compat_add_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('+%s' % (port))


def compat_del_bond_port(master, port):
    with open(_BONDING_SLAVES % (master), 'w') as f:
        f.write('-%s' % (port))


def compat_get_master(name):
    f = None

    for i in (_BRIDGE_MASTER, _BONDING_MASTER):
        try:
            f = open(i % (name))
            break
        except IOError:
            pass

    if f is not None:
        master = int(f.read())
        f.close()
        return master
