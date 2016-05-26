.. debug:

Netlink debug howto
-------------------

Dump data
=========

Either run the required command via `strace`, or attach to the running
process with `strace -p`. Use `-s {int}` argument to make sure that all
the messages are dumped. The `-x` argument instructs `strace` to produce
output in the hex format that can be passed to the pyroute2 decoder::

    $ strace -e trace=network -x -s 16384 ip ro
    socket(PF_NETLINK, SOCK_RAW|SOCK_CLOEXEC, NETLINK_ROUTE) = 3
    setsockopt(3, SOL_SOCKET, SO_SNDBUF, [32768], 4) = 0
    setsockopt(3, SOL_SOCKET, SO_RCVBUF, [1048576], 4) = 0
    bind(3, {sa_family=AF_NETLINK, pid=0, groups=00000000}, 12) = 0
    getsockname(3, {sa_family=AF_NETLINK, pid=28616, groups=00000000}, [12]) = 0
    sendto(3, "\x28\x00\x00\x00\x1a\x00\x01\x03 [skip] ", 40, 0, NULL, 0) = 40
    recvmsg(3, {msg_name(12)={sa_family=AF_NETLINK, pid=0, groups=00000000},
            msg_iov(1)=[{"\x3c\x00\x00\x00\x18 [skip]", 16384}],
            msg_controllen=0, msg_flags=0}, 0) = 480
    socket(PF_LOCAL, SOCK_DGRAM|SOCK_CLOEXEC, 0) = 4
    192.168.122.0/24 dev virbr0  proto kernel  scope link  src 192.168.122.1
    recvmsg(3, {msg_name(12)={sa_family=AF_NETLINK, pid=0, groups=00000000},
            msg_iov(1)=[{"\x14\x00\x00\x00\x03 [skip]", 16384}],
            msg_controllen=0, msg_flags=0}, 0) = 20
    +++ exited with 0 +++

Now you can copy `send…()` and `recv…()` buffer strings to a file.

Decode data
===========

The decoder is not provided with rpm or pip packages, so you should
have a local git repo of the project::

    $ git clone <url>
    $ cd pyroute2

Now run the decoder::

    $ export PYTHONPATH=`pwd`
    $ python tests/decoder/decoder.py <message.class> <data>

E.g. for the route dump in the file `rt.dump` the command line
should be::

    $ python tests/decoder/decoder.py \
        pyroute2.netlink.rtnl.rtmsg.rtmsg \
        rt.dump

**Why should I specify the message class?** Why there is no marshalling
in the decoder script? 'Cause it is intended to be used with different
netlink protocols, not only RTNL, but also nl80211, nfnetlink etc.
There is no common marshalling for all the netlink protocols.

**How to specify the message class?** All the netlink protocols are
defined under `pyroute2/netlink/`, e.g. `rtmsg` module is
`pyroute2/netlink/rtnl/rtmsg.py`. Thereafter you should specify the
class inside the module, since there can be several classes. In the
`rtmsg` case the line will be `pyroute.netlink.rtnl.rtmsg.rtmsg` or,
more friendly to the bash autocomplete, `pyroute2/netlink/rtnl/rtmsg.rtmsg`.
Notice, that the class you have to specify with dot anyways.

**What is the data file format?** Rules are as follows:

* The data dump should be in a hex format. Two possible variants are:
  `\\x00\\x01\\x02\\x03` or `00:01:02:03`.
* There can be several packets in the same file. They should be of the
  same type.
* Spaces and line ends are ignored, so you can format the dump as you
  want.
* The `#` symbol starts a comment until the end of the line.
* The `#!` symbols start a comment until the end of the file.

Example::

    # ifinfmsg headers
    #
    # nlmsg header
    \x84\x00\x00\x00  # length
    \x10\x00          # type
    \x05\x06          # flags
    \x49\x61\x03\x55  # sequence number
    \x00\x00\x00\x00  # pid
    # RTNL header
    \x00\x00          # ifi_family
    \x00\x00          # ifi_type
    \x00\x00\x00\x00  # ifi_index
    \x00\x00\x00\x00  # ifi_flags
    \x00\x00\x00\x00  # ifi_change
    # ...


Compile data
============

Starting with 0.4.1, the library provides `BatchSocket` class, that
only compiles and collects requests instead of sending them to the
kernel. E.g., it is used by `IPBatch`, that combines `BatchSocket`
with `IPRouteMixin`, providing RTNL compiler::

    $ python3
    Python 3.4.3 (default, Mar 31 2016, 20:42:37)
    [GCC 5.3.1 20151207 (Red Hat 5.3.1-2)] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    # import all the stuff
    >>> from pyroute2 import IPBatch
    >>> from pyroute2.common import hexdump
    # create the compiler
    >>> ipb = IPBatch()
    # compile requests into one buffer
    >>> ipb.link("add", index=550, kind="dummy", ifname="test")
    >>> ipb.link("set", index=550, state="up")
    >>> ipb.addr("add", index=550, address="10.0.0.2", mask=24)
    # inspect the buffer
    >>> hexdump(ipb.batch)
    '3c:00:00:00:10:00:05:06:00:00:00:00:a2:7c:00:00:00:00:00:00:
     26:02:00:00:00:00:00:00:00:00:00:00:09:00:03:00:74:65:73:74:
     00:00:00:00:10:00:12:00:0a:00:01:00:64:75:6d:6d:79:00:00:00:
     20:00:00:00:13:00:05:06:00:00:00:00:a2:7c:00:00:00:00:00:00:
     26:02:00:00:01:00:00:00:01:00:00:00:28:00:00:00:14:00:05:06:
     00:00:00:00:a2:7c:00:00:02:18:00:00:26:02:00:00:08:00:01:00:
     0a:00:00:02:08:00:02:00:0a:00:00:02'
    # reset the buffer
    >>> ipb.reset()

Pls notice, that in Python2 you should use `hexdump(str(ipb.batch))`
instead of `hexdump(ipb.batch)`.

The data, compiled by `IPBatch` can be used either to run batch
requests, when one `send()` call sends several messages at once, or
to produce binary buffers to test your own netlink parsers. Or just
to dump some data to be sent later and probably even on another host::

    >>> ipr = IPRoute()
    >>> ipr.sendto(ipb.batch, (0, 0))

The compiler always produces requests with `sequence_number == 0`,
so if there will be any responses, they can be handled as broadcasts.
