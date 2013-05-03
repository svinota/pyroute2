.. remote:

remote netlink
==============

Remote netlink allows you to communicate through the network
directly with the kernel of the remote system. E.g., running
on one node, the iproute module can allow you to monitor all
the network events on other node.

Remote netlink does not provide an API to create a messages on
the remote side. It just forwards netlink messages through the
network AS IS. Thus you should understand, that it is a great
risk: by running remote netlink server, you expose your OS
kernel to the network.

.. warning::
    Do **not** run remote netlink server unless you understand
    what are you doing and what risks there are.

.. note::
    To minimize risks, it is a good idea to use SSL/TLS connections.

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

supported transports
--------------------

Following schemes are supported:

* `tcp://hostname:port` -- plain TCP connection (**dangerous**)
* `tls://hostname:port` -- TLSv1 connection, requires certs on both sides
* `ssl://hostname:port` -- SSLv3 connection, requires certs on both sides
* `unix:///path/to/socket` -- AF_UNIX connection, within one system only
