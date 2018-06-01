# -*- coding: utf-8 -*-
'''

IPRoute quickstart
------------------

**IPRoute** in two words::

    $ sudo pip install pyroute2

    $ cat example.py
    from pyroute2 import IPRoute
    ip = IPRoute()
    print([x.get_attr('IFLA_IFNAME') for x in ip.get_links()])

    $ python example.py
    ['lo', 'p6p1', 'wlan0', 'virbr0', 'virbr0-nic']

IPRoute on Linux vs. BSD
------------------------

The pyroute2 library provides a simple RTNL API on FreeBSD and
OpenBSD systems as well. BSD systems have no netlink, so it is
implemented there with external utilities for requests and
PF_ROUTE socket for notifications. On BSD the IPRoute objects
spawn an additional thread when asked to monitor events.

On Linux systems RTNL API is provided by the netlink protocol,
so no implicit threads are started by default to monitor the
system updates. `IPRoute.bind(...)` may start the async cache
thread, but only when asked explicitly::

    #
    # Normal monitoring. Always starts monitoring thread on
    # FreeBSD / OpenBSD, but no threads on Linux.
    #
    with IPRoute() as ipr:
        ipr.bind()
        ...

    #
    # Monitoring with async cache. Always starts cache thread
    # on Linux, ignored on FreeBSD / OpenBSD.
    #
    with IPRoute() as ipr:
        ipr.bind(async_cache=True)
        ...

On all the supported platforms, be it Linux or BSD, the
`IPRoute.recv(...)` method returns valid netlink RTNL raw binary
payload and `IPRoute.get(...)` returns parsed RTNL messages.

Responses as lists
------------------

The netlink socket implementation in the pyroute2 is
agnostic to particular netlink protocols, and always returns
a list of messages as the response to a request sent to the
kernel::

    # this request returns one match
    eth0 = ipr.link_lookup(ifname='eth0')
    len(eth0)  # -> 1, if exists, else 0

    # but that one returns a set of
    up = ipr.link_lookup(operstate='UP')
    len(up)  # -> k, where 0 <= k <= [interface count]

Thus, always expect a list in the response, running any
`IPRoute()` netlink request.

NLMSG_ERROR responses
~~~~~~~~~~~~~~~~~~~~~

Some kernel subsystems return `NLMSG_ERROR` in response to
any request. It is OK as long as `nlmsg["header"]["error"] is None`.
Otherwise an exception will be raised by the parser.

So if instead of an exception you get a `NLMSG_ERROR` message,
it means `error == 0`, the same as `$? == 0` in bash.

How to work with messages
~~~~~~~~~~~~~~~~~~~~~~~~~

Every netlink message contains header, fields and NLAs
(netlink attributes). Every NLA is a netlink message...
(see "recursion").

And the library provides parsed messages according to
this scheme. Every RTNL message contains:

* `nlmsg['header']` -- parsed header
* `nlmsg['attrs']` -- NLA chain (parsed on demand)
* 0 .. k data fields, e.g. `nlmsg['flags']` etc.
* `nlmsg.header` -- the header fields spec
* `nlmsg.fields` -- the data fields spec
* `nlmsg.nla_map` -- NLA spec

An important parser feature is that NLAs are parsed
on demand, when someone tries to access them. Otherwise
the parser doesn't waste CPU cycles.

The NLA chain is a list-like structure, not a dictionary.
The netlink standard doesn't require NLAs to be unique
within one message::

    {'__align': (),
     'attrs': [('IFLA_IFNAME', 'lo'),    # [1]
               ('IFLA_TXQLEN', 1),
               ('IFLA_OPERSTATE', 'UNKNOWN'),
               ('IFLA_LINKMODE', 0),
               ('IFLA_MTU', 65536),
               ('IFLA_GROUP', 0),
               ('IFLA_PROMISCUITY', 0),
               ('IFLA_NUM_TX_QUEUES', 1),
               ('IFLA_NUM_RX_QUEUES', 1),
               ('IFLA_CARRIER', 1),
               ...],
     'change': 0,
     'event': 'RTM_NEWLINK',             # [2]
     'family': 0,
     'flags': 65609,
     'header': {'error': None,           # [3]
                'flags': 2,
                'length': 1180,
                'pid': 28233,
                'sequence_number': 257,  # [4]
                'type': 16},             # [5]
     'ifi_type': 772,
     'index': 1}

     # [1] every NLA is parsed upon access
     # [2] this field is injected by the RTNL parser
     # [3] if not None, an exception will be raised
     # [4] more details in the netlink description
     # [5] 16 == RTM_NEWLINK

To access fields::

    msg['index'] == 1

To access one NLA::

    msg.get_attr('IFLA_CARRIER') == 1

When the NLA with the specified name is not present in the
chain, `get_attr()` returns `None`. To get the list of all
NLAs of that name, use `get_attrs()`. A real example with
NLA hierarchy, take notice of `get_attr()` and
`get_attrs()` usage::

    # for macvlan interfaces there may be several
    # IFLA_MACVLAN_MACADDR NLA provided, so use
    # get_attrs() to get all the list, not only
    # the first one

    (msg
     .get_attr('IFLA_LINKINFO')           # one NLA
     .get_attr('IFLA_INFO_DATA')          # one NLA
     .get_attrs('IFLA_MACVLAN_MACADDR'))  # a list of

Pls read carefully the message structure prior to start the
coding.

Think about IPDB
----------------

If you plan to regularly fetch loads of objects, think
about IPDB also. Unlike to IPRoute, IPDB does not fetch
all the objects from OS every time you request them, but
keeps a cache that is asynchronously updated by the netlink
broadcasts. For a long-term running programs, that often
retrieve info about hundreds or thousands of objects, it
can be better to use IPDB as it will load CPU significantly
less.

API
---
'''
from pyroute2 import config
from pyroute2.iproute.linux import IPRouteMixin
from pyroute2.iproute.linux import IPBatch


if config.uname[0] == 'Linux':
    from pyroute2.iproute.linux import IPRoute
    from pyroute2.iproute.linux import RawIPRoute
elif config.uname[0][-3:] == 'BSD':
    from pyroute2.iproute.bsd import IPRoute
    from pyroute2.iproute.bsd import RawIPRoute
else:
    raise ImportError('no IPRoute module for the platform')

classes = [IPRouteMixin,
           IPBatch,
           IPRoute,
           RawIPRoute]
