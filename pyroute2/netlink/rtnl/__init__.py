'''
Developer's guide to Netlink and pyroute2

Generic netlink protocol
========================

General netlink packet structure::

    nlmsg packet:
        + header
        + data

Generic netlink message header::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid

The `length` field is the length of all the packet, including
data and header. The `type` field is used to distinguish different
message types, commands etc. Please note, that there is no
explicit protocol field -- you choose a netlink protocol, when
you create a socket.

The `sequence number` is very important. Netlink is an asynchronous
protocol -- it means, that the packet order doesn't matter. But
responses to a request are always marked with the same sequence
number, so you can treat it as a cookie.

Please keep in mind, that a netlink request can initiate a
cascade of events, and netlink messages from these events can
carry sequence number == 0. E.g., it is so when you remove a
primary IP addr from an interface, when `promote_secondaries`
sysctl is set.

Beside of incapsulated headers and other protocol-specific data,
netlink messages can carry NLA (netlink attributes). NLA
structure is as follows::

    NLA header:
        + uint16 length
        + uint16 type
    NLA data:
        + data-specific struct
        # optional:
        + NLA
        + NLA
        + ...

So, NLA structures can be nested, forming a tree.

Complete structure of a netlink packet::

    nlmsg header:
        + uint32 length
        + uint16 type
        + uint16 flags
        + uint32 sequence number
        + uint32 pid
    [ optional protocol-specific data ]
    [ optional NLA tree ]

More information about netlink protocol you can find in
the man pages.

Protocol sample: RTNL
=====================

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

Pyroute2 netlink description syntax
===================================

To simplify the development, pyroute2 provides an easy way to
describe packet structure. As an example, you can take the
ifaddrmsg description -- `pyroute2/netlink/rtnl/ifaddrmsg.py`.

To describe a packet, you need to inherit from `nlmsg` class::

    from pyroute2.netlink.generic import nlmsg

    class foo_msg(nlmsg):
        fields = ( ... )
        nla_map = ( ... )

NLA are described in the same way, but the parent class should be
`nla`, instead of `nlmsg`. And yes, it is important to use the
proper parent class.

fields attribute
++++++++++++++++

The `fields` attribute describes the structure of the
protocol-specific data. It is a tuple of tuples, where each
member contains a field name and its data format.

Field data format should be specified as for Python `struct`
module. E.g., ifaddrmsg structure::

    ifaddrmsg structure:
        + unsigned char ifa_family
        + unsigned char ifa_prefixlen
        + unsigned char ifa_flags
        + unsigned char ifa_scope
        + int ifa_index

should be described as follows::

    class ifaddrmsg(nlmsg):
        fields = (('family', 'B'),
                  ('prefixlen', 'B'),
                  ('flags', 'B'),
                  ('scope', 'B'),
                  ('index', 'I'))

Format strings are passed directly to the `struct` module,
so you can use all the notations like `>I`, `16s` etc. All
fields are parsed from the stream separately, so if you
want to explicitly fix alignemt, as if it were C struct,
use the `pack` attribute::

    class tstats(nla):
        pack = "struct"
        fields = (('version', 'H'),
                  ('ac_exitcode', 'I'),
                  ('ac_flag', 'B'),
                  ...)

nla_map attribute
+++++++++++++++++

The `nla_map` attribute is a tuple of NLA descriptions. Each
description is also a tuple in two different forms: either
two fields, name and format, or three fields: type, name and
format.

Please notice, that the format field is a string name of
corresponding NLA class::

    class ifaddrmsg(nlmsg):
        ...
        nla_map = (('IFA_UNSPEC',  'hex'),
                   ('IFA_ADDRESS', 'ipaddr'),
                   ('IFA_LOCAL', 'ipaddr'),
                   ...)

This code will create mapping, where IFA_ADDRESS NLA will be of
type 1 and IFA_LOCAL -- of type 2, etc. Both NLA will be decoded
as IP addresses (class `ipaddr`). IFA_UNSPEC will be of type 0,
and if it will be in the NLA tree, it will be just dumped in hex.

NLA class names are should be specified as strings, since they
are resolved in runtime.

There are several pre-defined NLA types, that you will get with
`nla` class:

* none  # forces pyroute2 just to skip this NLA
* uint8
* uint16
* uint32  # there are dedicated NLA of these types as well
* ipaddr  # IP address, IPv4 or IPv6, depending on the socket
* l2addr  # MAC address
* hex     # hex dump as a string -- useful for debugging
* cdata   # just a binary string
* asciiz  # zero-terminated ASCII string

Please refer to `pyroute2/netlink/generic.py` for details.

You can also make your own NLA descriptions::

    class ifaddrmsg(nlmsg):
        ...
        nla_map = (...
                   ('IFA_CACHEINFO', 'cacheinfo'),
                   ...)

        class cacheinfo(nla):
            fields = (('ifa_prefered', 'I'),
                      ('ifa_valid', 'I'),
                      ('cstamp', 'I'),
                      ('tstamp', 'I'))

Custom NLA descriptions should be defined in the same class,
where they are used.

Also, it is possible to use not autogenerated type numbers, as
for ifaddrmsg, but specify them explicitly::

    class iw_event(nla):
        ...
        nla_map = ((0x8B00, 'SIOCSIWCOMMIT', 'hex'),
                   (0x8B01, 'SIOCGIWNAME', 'hex'),
                   (0x8B02, 'SIOCSIWNWID', 'hex'),
                   (0x8B03, 'SIOCGIWNWID', 'hex'),
                   ...)

Here you can see custom NLA type numbers -- 0x8B00, 0x8B01 etc.
It is not permitted to mix these two forms in one class: you should
use ether autogenerated type numbers (two fields tuples), or
explicit numbers (three fields typles).

Parsed netlink message
======================

Netlink messages are represented by pyroute2 as dictionaries
as follows::

    {'header': {'pid': ...,
                'length: ...,
                'flags': ...,
                'error': None,  # if you are lucky
                'type': ...,
                'sequence_number': ...},

     # fields attributes
     'field_name1': value,
     ...
     'field_nameX': value,

     # nla tree
     'attrs': [['NLA_NAME1', value],
               ...
               ['NLA_NAMEX', value],
               ['NLA_NAMEY', {'field_name1': value,
                              ...
                              'field_nameX': value,
                              'attrs': [['NLA_NAME.... ]]}]]}

As an example, a message from the wireless subsystem about new
scan event::

    {'index': 4,
     'family': 0,
     '__align': 0,
     'header': {'pid': 0,
                'length': 64,
                'flags': 0,
                'error': None,
                'type': 16,
                'sequence_number': 0},
     'flags': 69699,
     'ifi_type': 1,
     'event': 'RTM_NEWLINK',
     'change': 0,
     'attrs': [['IFLA_IFNAME', 'wlp3s0'],
               ['IFLA_WIRELESS',
                {'attrs': [['SIOCGIWSCAN',
                            '00:00:00:00:00:00:00:00:00:00:00:00']]}]]}

Create and send a message
=========================

Using high-level interfaces like `IPRoute` or `IPDB`, you will never
need to manually construct and send netlink messages. But in the case
you really need it, it is simple as well.

Having a description class, like `ifaddrmsg` from above, you need to:

* instantiate it
* fill the fields
* encode the packet
* send the encoded data

The code::

    from pyroute2.netlink import NLM_F_REQUEST
    from pyroute2.netlink import NLM_F_ACK
    from pyroute2.netlink import NLM_F_CREATE
    from pyroute2.netlink import NLM_F_EXCL
    from pyroute2.netlink.iproute import RTM_NEWADDR
    from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg

    ##
    # add an addr to an interface
    #

    # create the message
    msg = ifaddrmsg()

    # fill the protocol-specific fields
    msg['index'] = index  # index of the interface
    msg['family'] = AF_INET  # address family
    msg['prefixlen'] = 24  # the address mask
    msg['scope'] = scope  # see /etc/iproute2/rt_scopes

    # attach NLA -- it MUST be a list / mutable
    msg['attrs'] = [['IFA_LOCAL', '192.168.0.1'],
                    ['IFA_ADDRESS', '192.162.0.1']]

    # fill generic netlink fields
    msg['header']['sequence_number'] = nonce  # an unique seq number
    msg['header']['pid'] = os.getpid()
    msg['header']['type'] = RTM_NEWADDR
    msg['header']['flags'] = NLM_F_REQUEST |\\
                             NLM_F_ACK |\\
                             NLM_F_CREATE |\\
                             NLM_F_EXCL

    # encode the packet
    msg.encode()

    # send the buffer
    nlsock.send(msg.buf.getvalue())

Please notice, that NLA list *MUST* be mutable.
'''

import os
import io
import time
import struct
import socket
import platform
import subprocess
from pyroute2.netlink import Marshal
from pyroute2.netlink import NetlinkSocket
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.common import map_namespace
from pyroute2.common import PipeSocket
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.rtnl.errmsg import errmsg
from pyroute2.netlink.rtnl.tcmsg import tcmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.brmsg import brmsg
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
               RTM_SETLINK: ifinfmsg,
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
               RTM_DELTFILTER: tcmsg,
               RTM_GETBRIDGE: brmsg,
               RTM_SETBRIDGE: brmsg}

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


class RtnlSocket(PipeSocket):

    def __init__(self):
        rfd, wfd = os.pipe()
        PipeSocket.__init__(self, rfd, wfd)
        self.marshal = MarshalRtnl()
        self.in_map = {RTM_NEWLINK: self.proxy_getlink}
        self.out_map = {RTM_NEWLINK: self.proxy_newlink,
                        RTM_SETLINK: self.proxy_setlink,
                        RTM_DELLINK: self.proxy_dellink,
                        RTM_SETBRIDGE: self.proxy_setbr}
        self.bypass = NetlinkSocket(NETLINK_ROUTE)
        self.iprs = IPRSocket()
        self.ancient = (platform.dist()[0] in ('redhat', 'centos') and
                        platform.dist()[1].startswith('6.'))

    def name_by_id(self, index):
        msg = ifinfmsg()
        msg['family'] = socket.AF_UNSPEC
        msg['header']['type'] = RTM_GETLINK
        msg['header']['flags'] = NLM_F_REQUEST
        msg['header']['pid'] = os.getpid()
        msg['header']['sequence_number'] = 1
        msg['index'] = index
        msg.encode()

        self.iprs.sendto(msg.buf.getvalue(), (0, 0))
        return self.iprs.get()[0].get_attr('IFLA_IFNAME')

    def bind(self, *argv, **kwarg):
        #
        # just proxy bind call -- PipeSocket by itself
        # doesn't need any bind() routine
        #
        self.bypass.bind(*argv, **kwarg)

    def get(self, fd, size):
        '''
        IOCore proxy protocol part
        '''
        data = fd.recv(size)
        #
        # extract type w/o parsing the message -- otherwise
        # we will repack every message
        #
        if len(data) < 6:
            return data

        mtype = struct.unpack('H', data[4:6])[0]
        if mtype in self.in_map:
            #
            # call an external hook
            #
            bio = io.BytesIO()
            bio.length = bio.write(data)
            msgs = self.marshal.parse(bio)
            return self.in_map[mtype](data, msgs)

        return data

    def sendto(self, data, addr):
        mtype = struct.unpack('H', data[4:6])[0]
        if mtype in self.out_map:
            #
            # call an external hook
            #
            bio = io.BytesIO()
            bio.length = bio.write(data)
            msg = self.marshal.parse(bio)[0]
            self.out_map[mtype](data, addr, msg)
        else:
            #
            # else send the data to the bypass socket
            #
            self.bypass.sendto(data, addr)

    def close(self):
        self.bypass.close()
        self.iprs.close()
        PipeSocket.close(self)

    ##
    # proxy hooks
    #
    def proxy_newlink(self, data, addr, msg):
        if self.ancient:
            # get the interface kind
            linkinfo = msg.get_attr('IFLA_LINKINFO')
            if linkinfo is not None:
                kind = linkinfo.get_attr('IFLA_INFO_KIND')
                # not covered types pass to the system
                if kind not in ('bridge', 'bond'):
                    return self.bypass.sendto(data, addr)
                ##
                # otherwise, create a valid answer --
                # NLMSG_ERROR with code 0 (no error)
                ##
                # FIXME: intercept and return valid RTM_NEWLINK
                ##
                response = ifinfmsg()
                response['header']['type'] = NLMSG_ERROR
                response['header']['sequence_number'] = \
                    msg['header']['sequence_number']
                # route the request
                if kind == 'bridge':
                    compat_create_bridge(msg.get_attr('IFLA_IFNAME'))
                elif kind == 'bond':
                    compat_create_bond(msg.get_attr('IFLA_IFNAME'))
                # while RTM_NEWLINK is not intercepted -- sleep
                time.sleep(_ANCIENT_BARRIER)
                response.encode()
                self.send(response.buf.getvalue())
        else:
            # else just send the packet
            self.bypass.sendto(data, addr)

    def proxy_getlink(self, data, msgs):
        if self.ancient:
            data = b''
            for msg in msgs:
                ifname = msg.get_attr('IFLA_IFNAME')
                master = compat_get_master(ifname)
                if master is not None:
                    msg['attrs'].append(['IFLA_MASTER', master])
                msg.reset()
                msg.encode()
                data += msg.buf.getvalue()
                del msg
        return data

    def proxy_setbr(self, data, addr, msg):
        #
        name = msg.get_attr('IFBR_IFNAME')
        code = 0
        # iterate commands:
        for (cmd, value) in msg.get_attr('IFBR_COMMANDS',
                                         {'attrs': []})['attrs']:
            cmd = brmsg.nla2name(cmd)
            code = compat_set_bridge(name, cmd, value) or code

        response = errmsg()
        response['header']['type'] = NLMSG_ERROR
        response['header']['sequence_number'] = \
            msg['header']['sequence_number']
        response['code'] = code
        response.encode()
        self.send(response.buf.getvalue())

    def proxy_setlink(self, data, addr, msg):
        # is it a port setup?
        master = msg.get_attr('IFLA_MASTER')
        if self.ancient and master is not None:
            response = ifinfmsg()
            response['header']['type'] = NLMSG_ERROR
            response['header']['sequence_number'] = \
                msg['header']['sequence_number']
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
            self.send(response.buf.getvalue())
        self.bypass.sendto(data, addr)

    def proxy_dellink(self, data, addr, msg):
        if self.ancient:
            # get the interface kind
            kind = compat_get_type(msg.get_attr('IFLA_IFNAME'))

            # not covered types pass to the system
            if kind not in ('bridge', 'bond'):
                return self.bypass.sendto(data, addr)
            ##
            # otherwise, create a valid answer --
            # NLMSG_ERROR with code 0 (no error)
            ##
            # FIXME: intercept and return valid RTM_NEWLINK
            ##
            response = ifinfmsg()
            response['header']['type'] = NLMSG_ERROR
            response['header']['sequence_number'] = \
                msg['header']['sequence_number']
            # route the request
            if kind == 'bridge':
                compat_del_bridge(msg.get_attr('IFLA_IFNAME'))
            elif kind == 'bond':
                compat_del_bond(msg.get_attr('IFLA_IFNAME'))
            # while RTM_NEWLINK is not intercepted -- sleep
            time.sleep(_ANCIENT_BARRIER)
            response.encode()
            self.send(response.buf.getvalue())
        else:
            # else just send the packet
            self.bypass.sendto(data, addr)


def compat_get_type(name):
    ##
    # is it bridge?
    try:
        open('/sys/class/net/%s/bridge/stp_state' % name, 'r')
        return 'bridge'
    except IOError:
        pass
    ##
    # is it bond?
    try:
        open('/sys/class/net/%s/bonding/mode' % name, 'r')
        return 'bond'
    except IOError:
        pass
    ##
    # don't care
    return 'unknown'


def compat_set_bridge(name, cmd, value):
    with open(os.devnull, 'w') as fnull:
        return subprocess.call(['brctl', cmd, name, str(value)],
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
