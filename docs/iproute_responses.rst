.. _iproute_responses:

.. testsetup:: *

   from pyroute2 import config

   config.mock_netlink = True

NLMSG_ERROR responses
---------------------

Some kernel subsystems return `NLMSG_ERROR` in response to any request.
This is acceptable as long as `nlmsg["header"]["error"]` is `None`.
If it is not `None`, an exception will be raised by the parser.

If you receive an `NLMSG_ERROR` message instead of an exception,
it means `error == 0`, which is equivalent to `$? == 0` in bash.

How to work with messages
-------------------------

Every netlink message contains a header, fields, and NLAs
(netlink attributes). Each NLA is itself a netlink message
(see "recursion").

The library parses messages according to this structure.
Each RTNL message includes the following:

* `nlmsg['header']` -- parsed header
* `nlmsg['attrs']` -- NLA chain (parsed on demand)
* data fields, e.g. `nlmsg['flags']` etc.
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

One key feature of the parser is that NLAs are parsed
only on demand, i.e., when accessed. This prevents
unnecessary CPU usage.

The NLA chain is a list-like structure rather than a
dictionary because the netlink standard does not require
NLAs to be unique within a single message::

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

To access fields or NLAs, use the `.get()` method. To retrieve
nested NLAs, pass a tuple of NLA names to the `.get()` call to
navigate through the hierarchy:

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

If an NLA with the specified name is not present in the chain,
`.get()` returns None. To retrieve a list of all NLAs with the
specified name, use `.get_attrs()`.

Below is an example demonstrating the usage of `.get()` and
`.get_attrs()` with an NLA hierarchy::

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

The protocol itself does not impose a limit on the number of NLAs
of the same type within a single message. This is why we cannot
represent them as a dictionary, unlike with `PF_ROUTE` messages.
