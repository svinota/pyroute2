# -*- coding: utf-8 -*-
'''
.. testsetup:: *

    from pyroute2 import config
    config.mock_netlink = True

API classes
-----------

AsyncIPRoute
~~~~~~~~~~~~

.. warning::
    The project core is being refactored right now, thus some
    methods may provide the old synchronous API. This will be
    fixed.

The main RTNL API class. Built upon the asyncio core. All
the methods that send netlink requests, are `async` and
return awaitables. The dump requests return async generators,
while other requests return iterables like tuples or lists.

The reason behind that is that RTNL dumps like routes or
neighbours may return so huge numbers of objects, so buffering
the whole response in the memory might be a bad idea.

.. testcode::

    import asyncio

    from pyroute2 import AsyncIPRoute


    async def main():
        async with AsyncIPRoute() as ipr:
            # create a link: immediate evaluation
            await ipr.link("add", ifname="test0", kind="dummy")

            # dump links: lazy evaluation
            async for link in await ipr.link("dump"):
                print(link.get("ifname"))

    asyncio.run(main())

.. testoutput::

    lo
    eth0
    test0

IPRoute
~~~~~~~

This API is planned be compatible with the old synchronous `IPRoute` from
versions 0.8.x and before:

.. testcode::

    from pyroute2 import IPRoute

    with IPRoute() as ipr:
        for msg in ipr.addr("dump"):
            addr = msg.get("address")
            mask = msg.get("prefixlen")
            print(f"{addr}/{mask}")

.. testoutput::

    127.0.0.1/8
    192.168.122.28/24

.. testcode::

    from pyroute2 import IPRoute

    with IPRoute() as ipr:

        # this request returns one match, one interface index
        eth0 = ipr.link_lookup(ifname="eth0")
        assert len(eth0) == 1  # 1 if exists else 0

        # this requests uses a lambda to filter interfaces
        # and returns all interfaces that are up
        nics_up = set(ipr.link_lookup(lambda x: x.get("flags") & 1))
        assert len(nics_up) == 2
        assert nics_up == {1, 2}


NetNS
~~~~~

NetNS class prior to 0.9.1 was used to run RTNL API in a network namespace.
Since pyroute2 0.9.1 the netns functionality is integrated in the library
core, so to run an `IPRoute` or `AsyncIPRoute` in a network namespace, simply
use `netns` argument:

.. testcode::

    from pyroute2 import IPRoute

    with IPRoute(netns="test") as ipr:
        assert ipr.status["netns"] == "test"

The current netns name is available as `.status["netns"]`.

The old synchronous `NetNS` class still is provided for compatibility,
but now it is but a wrapper around `IPRoute`.

.. testcode::

    from pyroute2 import NetNS

    with NetNS("test") as ns:
        assert ns.status["netns"] == "test"

NLMSG_ERROR responses
---------------------

Some kernel subsystems return `NLMSG_ERROR` in response to
any request. It is OK as long as `nlmsg["header"]["error"] is None`.
Otherwise an exception will be raised by the parser.

So if instead of an exception you get a `NLMSG_ERROR` message,
it means `error == 0`, the same as `$? == 0` in bash.

How to work with messages
-------------------------

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

..
    Test the attributes above:

.. testcode::
    :hide:

    from pyroute2 import IPRoute

    with IPRoute() as ipr:
        msg = tuple(ipr.link('dump'))[0]
        assert isinstance(msg['header'], dict)
        assert msg['header']['sequence_number'] > 0
        assert isinstance(msg['attrs'], list)
        assert isinstance(msg.header, tuple)
        assert isinstance(msg.fields, tuple)
        assert isinstance(msg.nla_map, tuple)
        assert len(msg['attrs']) > 0
        assert len(msg.header) == 5
        assert len(msg.fields) > 0
        assert len(msg.nla_map) > 0

An important parser feature is that NLAs are parsed
on demand, when someone tries to access them. Otherwise
the parser doesn't waste CPU cycles.

The NLA chain is a list-like structure, not a dictionary.
The netlink standard doesn't require NLAs to be unique
within one message::

    {'attrs': [('IFLA_IFNAME', 'lo'),    # [1]
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

To access fields or NLA, one can use `.get()`. To get nested NLA,
simply pass a tuple of NLA names to descend to the `.get()` call:

.. testcode::

    from pyroute2 import IPRoute

    with IPRoute() as ipr:
        lo = tuple(ipr.link("get", index=1))[0]
        # get a field
        assert lo.get("index") == 1
        # get an NLA
        assert lo.get("ifname") == "lo"
        # get a nested NLA
        assert lo.get(("stats64", "rx_bytes")) == 43309665

When an NLA with the specified name is not present in the
chain, `get()` returns `None`. To get the list of all
NLAs of that name, use `get_attrs()`. A real example with
NLA hierarchy, take notice of `get()` and
`get_attrs()` usage::

    # for macvlan interfaces there may be several
    # IFLA_MACVLAN_MACADDR NLA provided, so use
    # get_attrs() to get all the list, not only
    # the first one

    (msg
     .get('IFLA_LINKINFO')                # one NLA
     .get('IFLA_INFO_DATA')               # one NLA
     .get_attrs('IFLA_MACVLAN_MACADDR'))  # a list of

..
    FIXME! test the example above

The protocol itself has no limit for number of NLAs of the
same type in one message, that's why we can not make a dictionary
from them -- unlike PF_ROUTE messages.

'''
import sys

from pyroute2 import config
from pyroute2.iproute.linux import RTNL_API, IPBatch

# compatibility fix -- LNST:
from pyroute2.netlink.rtnl import (
    RTM_DELADDR,
    RTM_DELLINK,
    RTM_GETADDR,
    RTM_GETLINK,
    RTM_NEWADDR,
    RTM_NEWLINK,
)

AsyncIPRoute = None
if sys.platform.startswith('emscripten'):
    from pyroute2.iproute.ipmock import (
        ChaoticIPRoute,
        IPRoute,
        NetNS,
        RawIPRoute,
    )
elif sys.platform.startswith('win'):
    from pyroute2.iproute.windows import (
        ChaoticIPRoute,
        IPRoute,
        NetNS,
        RawIPRoute,
    )
elif config.uname[0][-3:] == 'BSD':
    from pyroute2.iproute.bsd import ChaoticIPRoute, IPRoute, NetNS, RawIPRoute
else:
    from pyroute2.iproute.linux import (
        AsyncIPRoute,
        ChaoticIPRoute,
        IPRoute,
        NetNS,
        RawIPRoute,
    )

classes = [
    AsyncIPRoute,
    RTNL_API,
    IPBatch,
    IPRoute,
    RawIPRoute,
    ChaoticIPRoute,
    NetNS,
]

constants = [
    RTM_GETLINK,
    RTM_NEWLINK,
    RTM_DELLINK,
    RTM_GETADDR,
    RTM_NEWADDR,
    RTM_DELADDR,
]
