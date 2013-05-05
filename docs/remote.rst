.. remote:

remote netlink
==============

Remote netlink allows you to communicate through the network
directly with the kernel of the remote system. E.g., running
on one node, the iproute module can allow you to monitor all
the network events on other node.

Remote netlink does not provide an API to create a messages on
the remote side. It just routes netlink messages through the
network.

.. warning::
    Do **not** run remote netlink server unless you understand
    what are you doing and what risks there are. Always, when
    it is possible, use SSL/TLS connections.

using ssl/tls
-------------

Create keys::

    $ sudo apt-get install openvpn
    $ cd $easy_rsa_2.0_dir
    $ make install DESTDIR=~/local/ssl
    $ cd ~/local/ssl
    $ vim vars
    $ . ./vars
    $ ./clean-all
    $ ./build-dh
    $ ./pkitool --initca
    $ ./pkitool --server server
    $ KEY_CN=`uuidgen` ./pkitool client
    ... copy client.key, client.crt, ca.crt to the client side
    ... copy server.key, server.crt, ca.crt to the server side

Sample server::

    from pyroute2 import iproute
    ip = iproute()
    ip.serve('tls://0.0.0.0:7000',
             key='server.key',
             cert='server.crt',
             ca='ca.crt')
    # the rest of the code -- server thread will run in the background

Sample client. Actually, you can use as a server or a client any
class, that is derived from base netlink class or build on the top
of it -- iproute, ipdb, taskstats etc.::

    from pyroute2 import ipdb
    ip = ipdb(host='tls://remote.host:7000',
              key='client.key',
              cert='client.crt',
              ca='ca.crt')
    with ip.tap0 as i:
        i.address = '00:11:22:33:44:55'
        i.ipaddr.add(('10.0.0.1', 24))
        i.ipaddr.add(('10.0.0.2', 24))
        i.ifname = 'vpn'

Or a sample with iproute::

    from pyroute2 import iproute
    ip = iproute(host='tls://remote.host:7000',
              key='client.key',
              cert='client.crt',
              ca='ca.crt')
    print ip.get_links()

why use ssl/tls?
----------------

There are two reasons to use SSL. First is the data encryption. But
more important is that pyroute2 enforces SSL client authentication.
In other words, a client **MUST** have the certificate, signed with
known CA. All other clients will be rejected. That's why one should
provide all three items in the client code -- key, cert and ca.

It is a good idea to use SSL/TLS over AF_UNIX sockets also, 'cause
of client authentication. In further releases pyroute2 will support
SASL authentication, but right now SSL/TLS is the only option.

supported transports
--------------------

Following schemes are supported:

* `tcp://hostname:port` -- plain TCP connection w/o auth (**dangerous**)
* `tls://hostname:port` -- TLSv1 connection, requires certs on both sides
* `ssl://hostname:port` -- SSLv3 connection, requires certs on both sides
* `unix:///path/to/socket` -- AF_UNIX connection, absolute path
* `unix://path/to/socket` -- AF_UNIX connection, relative path
* `unix://\\x00socket_id` -- AF_UNIX, abstract socket namespace
* `unix+[ssl|tls]://path/to/socket` -- AF_UNIX + SSL or TLS authentication

packet routing engine
---------------------

.. note::
    Following info is just reference information about pyroute2
    internal. You can skip it, unless you wanna extend pyroute2
    functionality.

Internal pyroute2 routing engine is implemented in `iothread` class.
It works with incoming packets as follows::

    select() → ready to read socket object

    is it incoming client connection?
        yes:
            establish the connection or drop it on error

    is it the in-process control socket?
        yes:
            parse control message, stop or reload the engine

    is it local netlink socket?
        yes:
            retranslate packet to clients
            parse the message

    is it remote client connection?
        yes:
            route client packet

    is it remote uplink connection?
        yes:
            parse the message


Client connection routing::

    is the message type NETLINK_UNUSED?
        yes:
            parse control message
        no:
            route message to the netlink socket

protocol
--------

Using pyroute2, you have nothing to do with underlying internals,
you're just using API. But if you wanna write software to
communicate with pyroute2, it is easy. Basically, remote netlink
protocol is nothing else than simple netlink messages, sent via
SOCK_STREAM connection. The only complicated part can be the
protocol negotiation, that contains SSL/TLS handshake and from
one (now) to several (future releases) control requests.

Remote netlink protocol scheme:

    1. ⇐⇒ [*optional*] SSL/TLS negotiation
    2. ⇐⇒ [*future|optional*] SASL authentication
    3.  ⇒ routing request
    4.  ⇒ [*future*] subscription request
    5. ⇐⇒ netlink messages

control messages
++++++++++++++++

All control messages between client and server should be done
in format of generic netlink command messages as follows:

========    ======  ================================================
field       size    note
========    ======  ================================================
**netlink header**
--------------------------------------------------------------------
length      uint32
type        uint16  for inter-pyroute2 connections -- NETLINK_UNUSED
flags       uint16  ignored
seq         uint32  sequence number, ignored
pid         uint32  client PID, ignored
--------------------------------------------------------------------
**generic netlink protocol**
--------------------------------------------------------------------
cmd         uint8   see possible commands below
version     uint8   ignored
reserved    uint16
========    ======  ================================================

Possible commands (**cmd** field):

=================   =====   ========================================
command             value   note
=================   =====   ========================================
IPRCMD_NOOP         1       ignored
IPRCMD_REGISTER     2       ignored
IPRCMD_UNREGISTER   3       ignored
IPRCMD_STOP         4       allowed only from the control connection
IPRCMD_RELOAD       5       allowed only from the control connection
IPRCMD_ROUTE        6       routing request
=================   =====   ========================================

Possible NLA:

=====================   ====    ====================================
NLA name                type    format
=====================   ====    ====================================
CTRL_ATTR_UNSPEC        0       none
CTRL_ATTR_FAMILY_ID     1       uint16
CTRL_ATTR_FAMILY_NAME   2       asciiz
=====================   ====    ====================================

routing request
+++++++++++++++

The routing request tells the server which netlink family the client
will use. So it should contain:

* message type == 1, NETLINK_UNUSED
* cmd == 6, IPRCMD_ROUTE
* one NLA CTRL_ATTR_FAMILY_ID == required family

For example, family NETLINK_ROUTE == 0, NETLINK_GENERIC == 16.

Please note, that pyroute2 does not start requested netlink socket
upon routing requests from clients. It just sets up routing to
existing netlink sockets -- or does not set, if there is no such
netlink socket yet.
