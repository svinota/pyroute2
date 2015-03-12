.. devgeneral:

It is easy to start to develop with pyroute2. In the simplest
case one just uses the library as is, and please do not
forget to file issues, bugs and feature requests to the
project github page.

If something should be changed in the library itself, and
you think you can do it, this document should help a bit.

Modules layout
==============

The library consists of several significant parts, and every
part has its own functionality::

    NetlinkSocket: connects the library to the OS
      ↑       ↑
      |       |
      |       ↓
      |     Marshal ←—→ Message classes
      |
      |
      ↓
    NL utility classes: more or less user-friendly API

NetlinkSocket and Marshal: :doc:`nlsocket`

NetlinkSocket
+++++++++++++

Notice, that it is possible to use a custom base class
instead of `socket.socket`. Thus, one can transparently
port this library to any different transport, or to use it
with `eventlet` library, that is not happy with
`socket.socket` objects, and so on.

Marshal
+++++++

A custom marshalling class can be required, if the protocol
uses some different marshalling algo from usual netlink.
Otherwise it is enough to use `register_policy` method of
the `NetlinkSocket`::

    # somewhere in a custom netlink class

    # dict key: message id, int
    # dict value: message class
    policy = {IPSET_CMD_PROTOCOL: ipset_msg,
              IPSET_CMD_LIST: ipset_msg}

    def __init__(self, ...):
        ...
        self.register_policy(policy)

But if just matching is not enough, refer to the `Marshal`
implementation. It is possible, e.g., to define the custom
`fix_message` method to be run on every message, etc. A
sample of such custom marshal can be found in the RTNL
implementation: `pyroute2.netlink.rtnl`.

Messages
++++++++

All the message classes hierarchy is built on the simple
fact that the netlink message structure is recursive in that
or other way.

A usual way to implement messages is described in the
netlink docs: :doc:`netlink`.

The core module, `pyroute2.netlink`, provides base classes
`nlmsg` and `nla`, as well as some other (`genlmsg`), and
basic NLA types: `uint32`, `be32`, `ip4addr`, `l2addr` etc.

One of the NLA types, `hex`, can be used to dump the NLA
structure in the hex format -- it is useful for development.

NL utility classes
++++++++++++++++++

They are based on different netlink sockets, such as
`IPRsocket` (RTNL), `NL80211` (wireless), or just
`NetlinkSocket` -- be it generic netlink or nfnetlink
(see taskstats and ipset).

Primarily, `pyroute2` is a netlink framework, so basic
classes and low-level utilities are intended to return
parsed netlink messages, not some user-friendly output.
So be not surprised.

But user-friendly modules are also possible and partly
provided, such as `IPDB`.

A list of low-level utility classes:

* `IPRoute` [`pyroute2.iproute`], RTNL utility like ip/tc
* `IPSet` [`pyroute2.ipset`], manipulate IP sets
* `IW` [`pyroute2.iwutil`], basic nl80211 support
* `NetNS` [`pyroute2.netns`], netns-enabled `IPRoute`
* `TaskStats` [`pyroute2.netlink.taskstats`], taskstats utility

High-level utilities:

* `IPDB` [`pyroute2.ipdb`], async IP database

Deferred imports
++++++++++++++++

The file `pyroute2/__init__.py` is a proxy for some modules,
thus providing a fixed import address, like::

    from pyroute2 import IPRoute
    ipr = IPRoute()
    ...
    ipr.close()

But not only. Actually, `pyroute2/__init__.py` exports not
classes and modules, but proxy objects, that load the actual
code in the runtime. The rationale is simple: in that way we
provide a possibility to use a custom base classes, see
`examples/custom_socket_base.py`.

Protocol debugging
++++++++++++++++++

The simplest way to start with some netlink protocol is to
use a reference implementation. Lets say we wrote the
`ipset_msg` class using the kernel code, and want to check
how it works. So the ipset(8) utility will be used as a
reference implementation::

    $ sudo strace -e trace=network -f -x -s 4096 ipset list
    socket(PF_NETLINK, SOCK_RAW, NETLINK_NETFILTER) = 3
    bind(3, {sa_family=AF_NETLINK, pid=0, groups=00000000}, 12) = 0
    getsockname(3, {sa_family=AF_NETLINK, pid=7009, groups=00000000}, [12]) = 0
    sendto(3, "\x1c\x00\x00\x00\x01\x06\x01\x00\xe3\x95\...
    recvmsg(3, {msg_name(12)={sa_family=AF_NETLINK, pid=0, groups=00000000},
        msg_iov(1)=[{"\x1c\x00\x00\x00\x01\x06\x00\x00\xe3\...
    sendto(3, "\x1c\x00\x00\x00\x07\x06\x05\x03\xe4\x95\...
    recvmsg(3, {msg_name(12)={sa_family=AF_NETLINK, pid=0, groups=00000000},
        msg_iov(1)=[{"\x78\x00\x00\x00\x07\x06\x02\x00\xe4\...

Here you can just copy packet strings from `sendto` and
`recvmsg`, place in a file and use `scripts/decoder.py` to
inspect them::

    $ export PYTHONPATH=`pwd`
    $ python scripts/decoder.py \
        pyroute2.netlink.nfnetlink.ipset.ipset_msg \
        scripts/ipset_01.data

See collected samples in the `scripts` directory. The script
ignores spaces and allows multiple messages in the same file.
