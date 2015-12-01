# -*- coding: utf-8 -*-
'''
IPRoute module
==============

iproute quickstart
------------------

**IPRoute** in two words::

    $ sudo pip install pyroute2

    $ cat example.py
    from pyroute2 import IPRoute
    ip = IPRoute()
    print([x.get_attr('IFLA_IFNAME') for x in ip.get_links()])

    $ python example.py
    ['lo', 'p6p1', 'wlan0', 'virbr0', 'virbr0-nic']

threaded vs. threadless architecture
------------------------------------

Since v0.3.2, IPRoute class is threadless by default.
It spawns no additional threads, and receives only
responses to own requests, no broadcast messages. So,
if you prefer not to cope with implicit threading, you
can safely use this module.

To get broadcast messages, use `IPRoute.bind()` call.
Please notice, that after calling `IPRoute.bind()` you
MUST get all the messages in time. In the case of the
kernel buffer overflow, you will have to restart the
socket.

With `IPRoute.bind(async=True)` one can launch async
message receiver thread with `Queue`-based buffer. The
buffer is thread-safe and completely transparent from
the programmer's perspective. Please read also
`NetlinkSocket` documentation to know more about async
mode.

think about IPDB
----------------

If you plan to regularly fetch loads of objects, think
about IPDB also. Unlike to IPRoute, IPDB does not fetch
all the objects from OS every time you request them, but
keeps a cache that is asynchronously updated by the netlink
broadcasts. For a long-term running programs, that often
retrieve info about hundreds or thousands of objects, it
can be better to use IPDB as it will load CPU significantly
less.

classes
-------
'''
import errno
import types
import logging
from socket import htons
from socket import AF_INET
from socket import AF_INET6
from socket import AF_UNSPEC
from types import FunctionType
from types import MethodType
from pyroute2.netlink import NetlinkError
from pyroute2.netlink import NLMSG_ERROR
from pyroute2.netlink import NLM_F_ATOMIC
from pyroute2.netlink import NLM_F_ROOT
from pyroute2.netlink import NLM_F_REPLACE
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_CREATE
from pyroute2.netlink import NLM_F_EXCL
from pyroute2.netlink.rtnl import RTM_NEWADDR
from pyroute2.netlink.rtnl import RTM_GETADDR
from pyroute2.netlink.rtnl import RTM_DELADDR
from pyroute2.netlink.rtnl import RTM_NEWLINK
from pyroute2.netlink.rtnl import RTM_GETLINK
from pyroute2.netlink.rtnl import RTM_DELLINK
from pyroute2.netlink.rtnl import RTM_NEWQDISC
from pyroute2.netlink.rtnl import RTM_GETQDISC
from pyroute2.netlink.rtnl import RTM_DELQDISC
from pyroute2.netlink.rtnl import RTM_NEWTFILTER
from pyroute2.netlink.rtnl import RTM_GETTFILTER
from pyroute2.netlink.rtnl import RTM_DELTFILTER
from pyroute2.netlink.rtnl import RTM_NEWTCLASS
from pyroute2.netlink.rtnl import RTM_GETTCLASS
from pyroute2.netlink.rtnl import RTM_DELTCLASS
from pyroute2.netlink.rtnl import RTM_NEWRULE
from pyroute2.netlink.rtnl import RTM_GETRULE
from pyroute2.netlink.rtnl import RTM_DELRULE
from pyroute2.netlink.rtnl import RTM_NEWROUTE
from pyroute2.netlink.rtnl import RTM_GETROUTE
from pyroute2.netlink.rtnl import RTM_DELROUTE
from pyroute2.netlink.rtnl import RTM_NEWNEIGH
from pyroute2.netlink.rtnl import RTM_GETNEIGH
from pyroute2.netlink.rtnl import RTM_DELNEIGH
from pyroute2.netlink.rtnl import RTM_SETLINK
from pyroute2.netlink.rtnl import RTM_GETNEIGHTBL
from pyroute2.netlink.rtnl import TC_H_INGRESS
from pyroute2.netlink.rtnl import TC_H_ROOT
from pyroute2.netlink.rtnl import rtprotos
from pyroute2.netlink.rtnl import rtypes
from pyroute2.netlink.rtnl import rtscopes
from pyroute2.netlink.rtnl.req import IPLinkRequest
from pyroute2.netlink.rtnl.tcmsg import get_htb_parameters
from pyroute2.netlink.rtnl.tcmsg import get_htb_class_parameters
from pyroute2.netlink.rtnl.tcmsg import get_tbf_parameters
from pyroute2.netlink.rtnl.tcmsg import get_sfq_parameters
from pyroute2.netlink.rtnl.tcmsg import get_u32_parameters
from pyroute2.netlink.rtnl.tcmsg import get_netem_parameters
from pyroute2.netlink.rtnl.tcmsg import get_fw_parameters
from pyroute2.netlink.rtnl.tcmsg import get_bpf_parameters
from pyroute2.netlink.rtnl.tcmsg import tcmsg
from pyroute2.netlink.rtnl.rtmsg import rtmsg
from pyroute2.netlink.rtnl.ndmsg import ndmsg
from pyroute2.netlink.rtnl.ndmsg import NUD_NAMES
from pyroute2.netlink.rtnl.ndtmsg import ndtmsg
from pyroute2.netlink.rtnl.fibmsg import fibmsg
from pyroute2.netlink.rtnl.fibmsg import FR_ACT_NAMES
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtnl.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl.iprsocket import IPRSocket
from pyroute2.netlink.rtnl.iprsocket import RawIPRSocket
from pyroute2.protocols import ETH_P_ALL

from pyroute2.common import basestring
from pyroute2.common import getbroadcast

DEFAULT_TABLE = 254


def transform_handle(handle):
    if isinstance(handle, basestring):
        (major, minor) = [int(x if x else '0', 16) for x in handle.split(':')]
        handle = (major << 8 * 2) | minor
    return handle


class IPRouteMixin(object):
    '''
    `IPRouteMixin` should not be instantiated by itself. It is intended
    to be used as a mixin class that provides iproute2-like API. You
    should use `IPRoute` or `NetNS` classes.

    All following info you can consider as IPRoute info as well.

    It is an old-school API, that provides access to rtnetlink as is.
    It helps you to retrieve and change almost all the data, available
    through rtnetlink::

        from pyroute2 import IPRoute
        ipr = IPRoute()
        # create an interface
        ipr.link_create(ifname='brx', kind='bridge')
        # lookup the index
        dev = ipr.link_lookup(ifname='brx')[0]
        # bring it down
        ipr.link('set', index=dev, state='down')
        # change the interface MAC address and rename it just for fun
        ipr.link('set', index=dev,
                 address='00:11:22:33:44:55',
                 ifname='br-ctrl')
        # add primary IP address
        ipr.addr('add', index=dev,
                 address='10.0.0.1', mask=24,
                 broadcast='10.0.0.255')
        # add secondary IP address
        ipr.addr('add', index=dev,
                 address='10.0.0.2', mask=24,
                 broadcast='10.0.0.255')
        # bring it up
        ipr.link('set', index=dev, state='up')
    '''

    def _match(self, match, msgs):
        # filtered results
        f_ret = []
        for msg in msgs:
            if isinstance(match, (FunctionType, MethodType)):
                if match(msg):
                    f_ret.append(msg)
            elif isinstance(match, dict):
                matches = []
                for key in match:
                    KEY = msg.name2nla(key)
                    if isinstance(match[key], types.FunctionType):
                        if msg.get(key) is not None:
                            matches.append(match[key](msg.get(key)))
                        elif msg.get_attr(KEY) is not None:
                            matches.append(match[key](msg.get_attr(KEY)))
                        else:
                            matches.append(False)
                    else:
                        matches.append(msg.get(key) == match[key] or
                                       msg.get_attr(KEY) ==
                                       match[key])
                if all(matches):
                    f_ret.append(msg)
        return f_ret

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
        Alias of `get_neighbours()`, deprecated.
        '''
        logging.warning('The `get_neighbors()` call is deprecated')
        logging.warning('Use `get_neighbours() instead')
        return self.get_neighbours(family)

    def get_neighbours(self, family=AF_UNSPEC, match=None, **kwarg):
        '''
        Dump ARP cache records.

        The `family` keyword sets the family for the request:
        e.g. `AF_INET` or `AF_INET6` for arp cache, `AF_BRIDGE`
        for fdb.

        If other keyword arguments not empty, they are used as
        filter. Also, one can explicitly set filter as a function
        with the `match` parameter.

        Examples::

            # get neighbours on the 3rd link:
            ip.get_neighbours(ifindex=3)

            # get a particular record by dst:
            ip.get_neighbours(dst='172.16.0.1')

            # get fdb records:
            ip.get_neighbours(AF_BRIDGE)

            # and filter them by a function:
            ip.get_neighbours(AF_BRIDGE, match=lambda x: x['state'] == 2)
        '''
        return self.neigh((RTM_GETNEIGH, NLM_F_REQUEST | NLM_F_DUMP),
                          family=family,
                          match=match or kwarg)

    def get_ntables(self, family=AF_UNSPEC):
        '''
        Get neighbour tables
        '''
        msg = ndtmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETNEIGHTBL)

    def get_addr(self, family=AF_UNSPEC, match=None, **kwarg):
        '''
        Dump addresses.

        If family is not specified, both AF_INET and AF_INET6 addresses
        will be dumped::

            # get all addresses
            ip.get_addr()

        It is possible to apply filters on the results::

            # get addresses for the 2nd interface
            ip.get_addr(index=2)

            # get addresses with IFA_LABEL == 'eth0'
            ip.get_addr(label='eth0')

            # get all the subnet addresses on the interface, identified
            # by broadcast address (should be explicitly specified upon
            # creation)
            ip.get_addr(index=2, broadcast='192.168.1.255')

        A custom predicate can be used as a filter::

            ip.get_addr(match=lambda x: x['index'] == 1)
        '''
        return self.addr((RTM_GETADDR, NLM_F_REQUEST | NLM_F_DUMP),
                         family=family,
                         match=match or kwarg)

    def get_rules(self, family=AF_UNSPEC, match=None, **kwarg):
        '''
        Get all rules. By default return all rules. To explicitly
        request the IPv4 rules use `family=AF_INET`.

        Example::
            ip.get_rules() # get all the rules for all families
            ip.get_rules(family=AF_INET6)  # get only IPv6 rules
        '''
        return self.rule((RTM_GETRULE,
                          NLM_F_REQUEST | NLM_F_ROOT | NLM_F_ATOMIC),
                         family=family,
                         match=match or kwarg)

    def get_routes(self, family=AF_UNSPEC, match=None, **kwarg):
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
        nkw = {}

        # get a particular route?
        if isinstance(kwarg.get('dst'), basestring):
            dlen = 32 if family == AF_INET else \
                128 if family == AF_INET6 else 0
            msg_flags = NLM_F_REQUEST
            nkw['dst'] = kwarg.pop('dst')
            nkw['dst_len'] = kwarg.pop('dst_len', dlen)

        return self.route((RTM_GETROUTE, msg_flags),
                          family=family, match=match or kwarg, **nkw)
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

    def link_create(self, **kwarg):
        '''
        Create a link. The method parameters will be
        passed to the `IPLinkRequest()` constructor as
        a dictionary.

        Examples::

            ip.link_create(ifname='very_dummy', kind='dummy')
            ip.link_create(ifname='br0', kind='bridge')
            ip.link_create(ifname='v101', kind='vlan', vlan_id=101, link=1)
        '''
        return self.link('add', **IPLinkRequest(kwarg))

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
        kwarg['table'] = kwarg.get('table', DEFAULT_TABLE)
        for route in self.get_routes(*argv, **kwarg):
            ret.append(self.nlm_request(route,
                                        msg_type=RTM_DELROUTE,
                                        msg_flags=flags))
        return ret

    def flush_addr(self, *argv, **kwarg):
        '''
        Flush addresses.

        Examples::

            # flush all addresses on the interface with index 2:
            ipr.flush_addr(index=2)

            # flush all addresses with IFA_LABEL='eth0':
            ipr.flush_addr(label='eth0')
        '''
        flags = NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL | NLM_F_REQUEST
        ret = []
        for addr in self.get_addr(*argv, **kwarg):
            try:
                ret.append(self.nlm_request(addr,
                                            msg_type=RTM_DELADDR,
                                            msg_flags=flags))
            except NetlinkError as e:
                if e.code != errno.EADDRNOTAVAIL:
                    raise
        return ret

    def flush_rules(self, *argv, **kwarg):
        '''
        Flush rules. Please keep in mind, that by default the function
        operates on **all** rules of **all** families. To work only on
        IPv4 rules, one should explicitly specify `family=AF_INET`.

        Examples::

            # flush all IPv4 rule with priorities above 5 and below 32000
            ipr.flush_rules(family=AF_INET, priority=lambda x: 5 < x < 32000)

            # flush all IPv6 rules that point to table 250:
            ipr.flush_rules(family=socket.AF_INET6, table=250)
        '''
        flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        ret = []
        for rule in self.get_rules(*argv, **kwarg):
            ret.append(self.nlm_request(rule,
                                        msg_type=RTM_DELRULE,
                                        msg_flags=flags))
        return ret
    # 8<---------------------------------------------------------------

    # 8<---------------------------------------------------------------
    #
    # General low-level configuration methods
    #
    def neigh(self, command, match=None, **kwarg):
        '''
        Neighbours operations, same as `ip neigh` or `bridge fdb`

        * command -- add, delete, change, replace
        * match -- match rules
        * ifindex -- device index
        * family -- family: AF_INET, AF_INET6, AF_BRIDGE
        * \*\*kwarg -- msg fields and NLA

        Example::

            pass
        '''
        # FIXME: this is only a draft; all definitions should
        # be generalized

        flags_base = NLM_F_REQUEST | NLM_F_ACK
        flags_make = flags_base | NLM_F_CREATE | NLM_F_EXCL
        flags_change = flags_base | NLM_F_REPLACE
        flags_replace = flags_change | NLM_F_CREATE

        commands = {'add': (RTM_NEWNEIGH, flags_make),
                    'set': (RTM_NEWNEIGH, flags_replace),
                    'replace': (RTM_NEWNEIGH, flags_replace),
                    'change': (RTM_NEWNEIGH, flags_change),
                    'del': (RTM_DELNEIGH, flags_make),
                    'remove': (RTM_DELNEIGH, flags_make),
                    'delete': (RTM_DELNEIGH, flags_make)}

        (command, flags) = commands.get(command, command)
        msg = ndmsg()
        for field in msg.fields:
            msg[field[0]] = kwarg.pop(field[0], 0)
        msg['family'] = msg['family'] or AF_INET
        msg['attrs'] = []
        # fix nud kwarg
        state = kwarg.pop('state', kwarg.pop('nud', 0))
        if isinstance(state, basestring):
            # parse state string
            states = state.split(',')
            state = 0
            for s in states:
                s = s.upper()
                if not s.startswith('NUD_'):
                    s = 'NUD_' + s
                state |= NUD_NAMES[s]
        msg['state'] = state

        for key in kwarg:
            nla = ndmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        ret = self.nlm_request(msg, msg_type=command, msg_flags=flags)
        if match is not None:
            return self._match(match, ret)
        else:
            return ret

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

        commands = {'set': RTM_SETLINK,
                    'add': RTM_NEWLINK,
                    'del': RTM_DELLINK,
                    'remove': RTM_DELLINK,
                    'delete': RTM_DELLINK}
        command = commands.get(command, command)

        msg_flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        if not isinstance(kwarg['index'], int):
            raise ValueError('index should be int')
        msg = ifinfmsg()
        # index is required
        msg['index'] = kwarg['index']

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
            nla = type(msg).name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        def update_caps(e):
            # update capabilities, if needed
            if e.code == errno.EOPNOTSUPP:
                kind = None
                li = msg.get_attr('IFLA_LINKINFO')
                if li:
                    attrs = li.get('attrs', [])
                    for attr in attrs:
                        if attr[0] == 'IFLA_INFO_KIND':
                            kind = attr[1]
                if kind == 'bond' and self.capabilities['create_bond']:
                    self.capabilities['create_bond'] = False
                    return
                if kind == 'bridge' and self.capabilities['create_bridge']:
                    self.capabilities['create_bridge'] = False
                    return

            # let the exception to be forwarded
            return True

        return self.nlm_request(msg,
                                msg_type=command,
                                msg_flags=msg_flags,
                                exception_catch=NetlinkError,
                                exception_handler=update_caps)

    def addr(self, command, index=None, address=None, mask=None,
             family=None, scope=None, match=None, **kwarg):
        '''
        Address operations

        * command -- add, delete
        * index -- device index
        * address -- IPv4 or IPv6 address
        * mask -- address mask
        * family -- socket.AF_INET for IPv4 or socket.AF_INET6 for IPv6
        * scope -- the address scope, see /etc/iproute2/rt_scopes
        * \*\*kwarg -- any ifaddrmsg field or NLA

        Later the method signature will be changed to::

            def addr(self, command, match=None, **kwarg):
                # the method body

        So only keyword arguments (except of the command) will be accepted.
        The reason for this change is an unification of API.

        Example::

            idx = 62
            ip.addr('add', index=idx, address='10.0.0.1', mask=24)
            ip.addr('add', index=idx, address='10.0.0.2', mask=24)

        With more NLAs::

            # explicitly set broadcast address
            ip.addr('add', index=idx,
                    address='10.0.0.3',
                    broadcast='10.0.0.255',
                    prefixlen=24)

            # make the secondary address visible to ifconfig: add label
            ip.addr('add', index=idx,
                    address='10.0.0.4',
                    broadcast='10.0.0.255',
                    prefixlen=24,
                    label='eth0:1')
        '''

        flags_create = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
        commands = {'add': (RTM_NEWADDR, flags_create),
                    'del': (RTM_DELADDR, flags_create),
                    'remove': (RTM_DELADDR, flags_create),
                    'delete': (RTM_DELADDR, flags_create)}
        (command, flags) = commands.get(command, command)

        # fetch args
        index = index or kwarg.pop('index', 0)
        family = family or kwarg.pop('family', None)
        prefixlen = mask or kwarg.pop('mask', 0) or kwarg.pop('prefixlen', 0)
        scope = scope or kwarg.pop('scope', 0)

        # move address to kwarg
        # FIXME: add deprecation notice
        if address:
            kwarg['address'] = address

        # try to guess family, if it is not forced
        if kwarg.get('address') and family is None:
            if address.find(":") > -1:
                family = AF_INET6
                mask = mask or 128
            else:
                family = AF_INET
                mask = mask or 24

        # setup the message
        msg = ifaddrmsg()
        msg['index'] = index
        msg['family'] = family or 0
        msg['prefixlen'] = prefixlen
        msg['scope'] = scope

        # inject IFA_LOCAL, if family is AF_INET
        if family == AF_INET and kwarg.get('address'):
            kwarg['local'] = kwarg['address']

        # patch broadcast, if needed
        if kwarg.get('broadcast') is True:
            kwarg['broadcast'] = getbroadcast(address, mask, family)

        # work on NLA
        for key in kwarg:
            nla = ifaddrmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        ret = self.nlm_request(msg,
                               msg_type=command,
                               msg_flags=flags,
                               terminate=lambda x: x['header']['type'] ==
                               NLMSG_ERROR)
        if match:
            return self._match(match, ret)
        else:
            return ret

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

        Target notice: if your target is a class/qdisc that applies an
        algorithm that can only apply to upstream traffic profile, but your
        keys variable explicitly references a match that is only relevant for
        upstream traffic, the kernel will reject the filter.  Unless you're
        dealing with devices like IMQs

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
            flags = NLM_F_REQUEST | NLM_F_ACK | NLM_F_CREATE | NLM_F_EXCL
            ip.tc((RTM_NEWQDISC, flags), "sfq", 1)

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

        Filters can also take an `action` argument, which affects the packet
        behavior when the filter matches. Currently the gact, bpf, and police
        action types are supported, and can be attached to the u32 and bpf
        filter types::

            # An action can be a simple string, which translates to a gact type
            action = "drop"

            # Or it can be an explicit type (these are equivalent)
            action = dict(kind="gact", action="drop")

            # There can also be a chain of actions, which depend on the return
            # value of the previous action.
            action = [
                dict(kind="bpf", fd=fd, name=name, action="ok"),
                dict(kind="police", rate="10kbit", burst=10240, limit=0),
                dict(kind="gact", action="ok"),
            ]

            # Add the action to a u32 match-all filter
            ip.tc("add", "htb", eth0, 0x10000, default=0x200000)
            ip.tc("add-filter", "u32", eth0,
                  parent=0x10000,
                  prio=10,
                  protocol=protocols.ETH_P_ALL,
                  target=0x10020,
                  keys=["0x0/0x0+0"],
                  action=action)

            # Add two more filters: One to send packets with a src address of
            # 192.168.0.1/32 into 1:10 and the second to send packets  with a
            # dst address of 192.168.0.0/24 into 1:20
            ip.tc("add-filter", "u32", eth0,
                parent=0x10000,
                prio=10,
                protocol=socket.AF_INET,
                target=0x10010,
                keys=["0xc0a80001/0xffffffff+12"])
                # 0xc0a800010 = 192.168.0.1
                # 0xffffffff = 255.255.255.255 (/32)
                # 12 = Source network field bit offset

            ip.tc("add-filter", "u32", eth0,
                parent=0x10000,
                prio=10,
                protocol=socket.AF_INET,
                target=0x10020,
                keys=["0xc0a80000/0xffffff00+16"])
                # 0xc0a80000 = 192.168.0.0
                # 0xffffff00 = 255.255.255.0 (/24)
                # 16 = Destination network field bit offset
        '''
        flags_base = NLM_F_REQUEST | NLM_F_ACK
        flags_make = flags_base | NLM_F_CREATE | NLM_F_EXCL
        flags_change = flags_base | NLM_F_REPLACE
        flags_replace = flags_change | NLM_F_CREATE

        commands = {'add': (RTM_NEWQDISC, flags_make),
                    'del': (RTM_DELQDISC, flags_make),
                    'remove': (RTM_DELQDISC, flags_make),
                    'delete': (RTM_DELQDISC, flags_make),
                    'add-class': (RTM_NEWTCLASS, flags_make),
                    'del-class': (RTM_DELTCLASS, flags_make),
                    'change-class': (RTM_NEWTCLASS, flags_change),
                    'replace-class': (RTM_NEWTCLASS, flags_replace),
                    'add-filter': (RTM_NEWTFILTER, flags_make),
                    'del-filter': (RTM_DELTFILTER, flags_make),
                    'change-class': (RTM_NEWTFILTER, flags_change),
                    'replace-filter': (RTM_NEWTFILTER, flags_replace)}
        if isinstance(command, int):
            command = (command, flags_make)
        command, flags = commands.get(command, command)
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
        elif kind == 'bpf':
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)
            msg['info'] = htons(kwarg.get('protocol', ETH_P_ALL) & 0xffff) |\
                ((kwarg.get('prio', 0) << 16) & 0xffff0000)
            if kwarg:
                opts = get_bpf_parameters(kwarg)
        else:
            msg['parent'] = kwarg.get('parent', TC_H_ROOT)

        if kind is not None:
            msg['attrs'] = [['TCA_KIND', kind]]
        if opts is not None:
            msg['attrs'].append(['TCA_OPTIONS', opts])
        return self.nlm_request(msg, msg_type=command, msg_flags=flags)

    def route(self, command, **kwarg):
        '''
        Route operations.

        * command -- add, delete, change, replace
        * rtype -- route type (default: "RTN_UNICAST")
        * rtproto -- routing protocol (default: "RTPROT_STATIC")
        * rtscope -- routing scope (default: "RT_SCOPE_UNIVERSE")
        * family -- socket.AF_INET (default) or socket.AF_INET6
        * mask -- route prefix mask

        `pyroute2/netlink/rtnl/rtmsg.py` rtmsg.nla_map:

        * table -- routing table to use (default: 254)
        * gateway -- via address
        * prefsrc -- preferred source IP address
        * dst -- the same as `prefix`
        * src -- source address
        * iif -- incoming traffic interface
        * oif -- outgoing traffic interface

        etc.

        Example::

            ip.route("add", dst="10.0.0.0", mask=24, gateway="192.168.0.1")

        Commands `change` and `replace` have the same meanings, as
        in ip-route(8): `change` modifies only existing route, while
        `replace` creates a new one, if there is no such route yet.

        It is possible to set also route metrics. There are two ways
        to do so. The first is to use 'raw' NLA notation::

            ip.route("add",
                     dst="10.0.0.0",
                     mask=24,
                     gateway="192.168.0.1",
                     metrics={"attrs": [["RTAX_MTU", 1400],
                                        ["RTAX_HOPLIMIT", 16]]})

        The second way is to use `IPRouteRequest` helper::

            from pyroute2.netlink.rtnl.req import IPRouteRequest
            ...
            ip.route("add", **IPRouteRequest({"dst": "10.0.0.0/24",
                                              "gateway": "192.168.0.1",
                                              "metrics": {"mtu": 1400,
                                                          "hoplimit": 16}}))

        The `IPRouteRequest` helper is useful also to manage
        mulptipath routes::

            from pyroute2.netlink.rtnl.req import IPRouteRequest
            ...
            request = {"dst": "10.0.0.0/24",
                       "multipath": [{"gateway": "192.168.0.1",
                                      "hops": 2},
                                     {"gateway": "192.168.0.2",
                                      "hops": 1},
                                     {"gateway": "192.168.0.3"}]}
            ip.route("add", **IPRouteRequest(request))
        '''

        # 8<----------------------------------------------------
        # FIXME
        # flags should be moved to some more general place
        flags_base = NLM_F_REQUEST | NLM_F_ACK
        flags_make = flags_base | NLM_F_CREATE | NLM_F_EXCL
        flags_change = flags_base | NLM_F_REPLACE
        flags_replace = flags_change | NLM_F_CREATE
        # 8<----------------------------------------------------
        commands = {'add': (RTM_NEWROUTE, flags_make),
                    'set': (RTM_NEWROUTE, flags_replace),
                    'replace': (RTM_NEWROUTE, flags_replace),
                    'change': (RTM_NEWROUTE, flags_change),
                    'del': (RTM_DELROUTE, flags_make),
                    'remove': (RTM_DELROUTE, flags_make),
                    'delete': (RTM_DELROUTE, flags_make)}
        (command, flags) = commands.get(command, command)
        msg = rtmsg()
        # table is mandatory; by default == 254
        # if table is not defined in kwarg, save it there
        # also for nla_attr:
        table = kwarg.get('table', 254)
        msg['table'] = table if table <= 255 else 252
        msg['family'] = kwarg.pop('family', AF_INET)
        msg['proto'] = rtprotos[kwarg.pop('rtproto', 'RTPROT_STATIC')]
        msg['type'] = rtypes[kwarg.pop('rtype', 'RTN_UNICAST')]
        msg['scope'] = rtscopes[kwarg.pop('rtscope', 'RT_SCOPE_UNIVERSE')]
        msg['dst_len'] = kwarg.pop('dst_len', None) or kwarg.pop('mask', 0)
        msg['src_len'] = kwarg.pop('src_len', 0)
        msg['tos'] = kwarg.pop('tos', 0)
        msg['flags'] = kwarg.pop('flags', 0)
        msg['attrs'] = []
        # FIXME
        # deprecated "prefix" support:
        if 'prefix' in kwarg:
            logging.warning('`prefix` argument is deprecated, use `dst`')
            kwarg['dst'] = kwarg['prefix']

        for key in kwarg:
            nla = rtmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])
                # fix IP family, if needed
                if msg['family'] == AF_UNSPEC:
                    if key in ('dst', 'src', 'gateway', 'prefsrc', 'newdst') \
                            and isinstance(kwarg[key], basestring):
                        msg['family'] = AF_INET6 if kwarg[key].find(':') >= 0 \
                            else AF_INET
                    elif key == 'multipath' and len(kwarg[key]) > 0:
                        hop = kwarg[key][0]
                        attrs = hop.get('attrs', [])
                        for attr in attrs:
                            if attr[0] == 'RTA_GATEWAY':
                                msg['family'] = AF_INET6 if \
                                    attr[1].find(':') >= 0 else AF_INET
                                break

        ret = self.nlm_request(msg, msg_type=command, msg_flags=flags)
        if 'match' in kwarg:
            return self._match(kwarg['match'], ret)
        else:
            return ret

    def rule(self, command, *argv, **kwarg):
        '''
        Rule operations

            - command — add, delete
            - table — 0 < table id < 253
            - priority — 0 < rule's priority < 32766
            - action — type of rule, default 'FR_ACT_NOP' (see fibmsg.py)
            - rtscope — routing scope, default RT_SCOPE_UNIVERSE
                `(RT_SCOPE_UNIVERSE|RT_SCOPE_SITE|\
                RT_SCOPE_LINK|RT_SCOPE_HOST|RT_SCOPE_NOWHERE)`
            - family — rule's family (socket.AF_INET (default) or
                socket.AF_INET6)
            - src — IP source for Source Based (Policy Based) routing's rule
            - dst — IP for Destination Based (Policy Based) routing's rule
            - src_len — Mask for Source Based (Policy Based) routing's rule
            - dst_len — Mask for Destination Based (Policy Based) routing's
                rule
            - iifname — Input interface for Interface Based (Policy Based)
                routing's rule
            - oifname — Output interface for Interface Based (Policy Based)
                routing's rule

        All packets route via table 10::

            # 32000: from all lookup 10
            # ...
            ip.rule('add', table=10, priority=32000)

        Default action::

            # 32001: from all lookup 11 unreachable
            # ...
            iproute.rule('add',
                         table=11,
                         priority=32001,
                         action='FR_ACT_UNREACHABLE')

        Use source address to choose a routing table::

            # 32004: from 10.64.75.141 lookup 14
            # ...
            iproute.rule('add',
                         table=14,
                         priority=32004,
                         src='10.64.75.141')

        Use dst address to choose a routing table::

            # 32005: from 10.64.75.141/24 lookup 15
            # ...
            iproute.rule('add',
                         table=15,
                         priority=32005,
                         dst='10.64.75.141',
                         dst_len=24)

        Match fwmark::

            # 32006: from 10.64.75.141 fwmark 0xa lookup 15
            # ...
            iproute.rule('add',
                         table=15,
                         priority=32006,
                         dst='10.64.75.141',
                         fwmark=10)
        '''
        flags_base = NLM_F_REQUEST | NLM_F_ACK
        flags_make = flags_base | NLM_F_CREATE | NLM_F_EXCL
        flags_change = flags_base | NLM_F_REPLACE
        flags_replace = flags_change | NLM_F_CREATE

        commands = {'add': (RTM_NEWRULE, flags_make),
                    'del': (RTM_DELRULE, flags_make),
                    'remove': (RTM_DELRULE, flags_make),
                    'delete': (RTM_DELRULE, flags_make),
                    'change': (RTM_NEWRULE, flags_change),
                    'replace': (RTM_NEWRULE, flags_replace)}
        if isinstance(command, int):
            command = (command, flags_make)
        command, flags = commands.get(command, command)

        if argv:
            # this code block will be removed in some release
            logging.warning('rule(): positional parameters are deprecated')
            names = ['table', 'priority', 'action', 'family',
                     'src', 'src_len', 'dst', 'dst_len', 'fwmark',
                     'iifname', 'oifname']
            kwarg.update(dict(zip(names, argv)))
        msg = fibmsg()
        table = kwarg.get('table', 254)
        msg['table'] = table if table <= 255 else 252
        msg['family'] = family = kwarg.pop('family', AF_INET)
        msg['action'] = FR_ACT_NAMES[kwarg.pop('action', 'FR_ACT_NOP')]
        msg['attrs'] = []

        addr_len = {AF_INET6: 128, AF_INET:  32}.get(family, 0)
        if 'priority' not in kwarg:
            kwarg['priority'] = 32000
        if ('src' in kwarg) and (kwarg.get('src_len') is None):
            kwarg['src_len'] = addr_len
        if ('dst' in kwarg) and (kwarg.get('dst_len') is None):
            kwarg['dst_len'] = addr_len

        msg['dst_len'] = kwarg.get('dst_len', 0)
        msg['src_len'] = kwarg.get('src_len', 0)

        for key in kwarg:
            nla = fibmsg.name2nla(key)
            if kwarg[key] is not None:
                msg['attrs'].append([nla, kwarg[key]])

        ret = self.nlm_request(msg, msg_type=command, msg_flags=flags)

        if 'match' in kwarg:
            return self._match(kwarg['match'], ret)
        else:
            return ret
    # 8<---------------------------------------------------------------


class IPRoute(IPRouteMixin, IPRSocket):
    '''
    Production class that provides iproute API over normal Netlink
    socket.

    You can think of this class in some way as of plain old iproute2
    utility.
    '''
    pass


class RawIPRoute(IPRouteMixin, RawIPRSocket):
    pass
