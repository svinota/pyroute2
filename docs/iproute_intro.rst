.. _iproute_intro:

.. testsetup:: *

   from pyroute2 import config

   config.mock_netlink = True


RTNL classes
------------

**Arguments** to the constructors:

port: `Optional[int]`
    An integer to be used together with `pid` in the `bind()`
    call, `epid = pid + (port << 22)`.

pid: `Optional[int]`
    Value to be used as the base in while calling `bind()`

fileno: `Optional[int]`
    An open file descriptor to construct the socket from.

sndbuf: `int`
    Send buffer limit in bytes.

rcvbuf: `int`
    Receive buffer limit in bytes.

rcvsize: `int`
    Maximum recieve packet size.

all_ns: `bool`
    Turns on `NETLINK_LISTEN_ALL_NSID` on the socket.

async_qsize
    Deprecated.

nlm_generator
    Deprecated.

target: `str`
    Target field (string) to be provided in the header. Useful
    when working with sockets in multiple network namespaces.

ext_ack: `bool`
    Extended ACK controls reporting additional error or warning
    info in `NLMSG_ERROR` and `NLMSG_DONE` messages.

strict_check: `bool`
    Controls strict input field checking. By default kernel does
    not validate the input fields, silently ignoring possible
    issues, that may lead to regressions in the future.

groups: `int` (default: `pyroute2.netlink.rtnl.RTMGRP_DEFAULTS`)
    Groups to subscribe when calling `bind()`, see `pyroute2.netlink.rtnl`

nlm_echo: `bool`
    Return the request fields in the response.

use_socket: `Optional[socket.socket]`
    An existing socket object to run the protocol on.

netns: `str`
    Network namespace to use.

flags: `int` (default: `os.O_CREAT`)
    Flags to use when calling `netns.create()`. By default the
    library will create netns if it doesn't exist, and reuse if
    it does. In order to fail when the network namespace already
    exists, you should provide `flags=0`.

libc: `Optional[ctypes.CDLL]`
    If you want the socket to use specific libc object when managing
    network namespaces, you can use this argument.

use_event_loop: `Optional[asyncio.AbstractEventLoop]`
    Use an existing asyncio event loop.

**RTNL classes**:

.. autoclass:: pyroute2.AsyncIPRSocket

.. autoclass:: pyroute2.IPRSocket

.. autoclass:: pyroute2.AsyncIPRoute

.. autoclass:: pyroute2.IPRoute

.. autoclass:: pyroute2.NetNS
