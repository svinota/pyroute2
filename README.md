![E/// logo](docs/ericsson.png "supported by Ericsson")

pyroute2
========

Pyroute2 is a pure Python **netlink** and Linux **network configuration**
library. It requires only Python stdlib, no 3rd party libraries.
Later it can change, but the deps tree will remain as simple, as
it is possible.

The library provides several modules:

* Netlink protocol implementations (RTNetlink, TaskStats, etc)
    * **rtnl**, network settings --- addresses, routes, traffic controls
    * **nl80211** --- wireless functions API (work in progress)
    * **nfnetlink** --- netfilter API: **ipset**, **nftables** (work in progress), ...
    * **ipq** --- simplest userspace packet filtering, iptables QUEUE target
    * **taskstats** --- extended process statistics
* Simple netlink socket object, that can be used in poll/select
* Network configuration module IPRoute provides API that in some
  way resembles ip/tc functionality
* IPDB is an async transactional database of Linux network settings

rtnetlink sample
----------------

More samples you can read in the project documentation.

Low-level **IPRoute** utility --- Linux network configuration.
The **IPRoute** class is a 1-to-1 RTNL mapping. There are no implicit
interface lookups and so on.

Some examples::

    from socket import AF_INET
    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print(ip.get_links())

    # create VETH pair and move v0p1 to netns 'test'
    ip.link_create(ifname='v0p0', peer='v0p1', kind='veth')
    idx = ip.link_lookup(ifname='v0p1')[0]
    ip.link('set',
            index=idx,
            net_ns_fd='test')

    # bring v0p0 up and add an address
    idx = ip.link_lookup(ifname='v0p0')[0]
    ip.link('set',
            index=idx,
            state='up')
    ip.addr('add',
            index=idx,
            address='10.0.0.1',
            broadcast='10.0.0.255',
            prefixlen=24)

    # create a route with metrics
    ip.route('add',
             dst='172.16.0.0/24',
             gateway='10.0.0.10',
             metrics={'mtu': 1400,
                      'hoplimit': 16})

    # create MPLS lwtunnel
    # $ sudo modprobe mpls_iptunnel
    ip.route('add',
             dst='172.16.0.0/24',
             oif=idx,
             encap={'type': 'mpls',
                    'labels': '200/300'})

    # create MPLS route: push label
    # $ sudo modprobe mpls_router
    # $ sudo sysctl net.mpls.platform_labels=1024
    ip.route('add',
             family=AF_MPLS,
             oif=idx,
             dst=0x200,
             newdst=[0x200, 0x300])

    # release Netlink socket
    ip.close()


High-level transactional interface, **IPDB**, a network settings DB::

    from pyroute2 import IPDB
    #
    # The `with` statement automatically calls `IPDB.release()`
    # in the case of an exception.
    with IPDB() as ip:
        #
        # Create bridge and add ports and addresses.
        #
        # Transaction will be started by `with` statement
        # and will be committed at the end of the block
        with ip.create(kind='bridge', ifname='rhev') as i:
            i.add_port('em1')
            i.add_port('em2')
            i.add_ip('10.0.0.2/24')
        # --> <-- Here the system state is as described in
        #         the transaction, if no error occurs. If
        #         there is an error, all the changes will be
        #         rolled back.

The IPDB arch allows to use it transparently with network
namespaces::

    from pyroute2 import IPDB
    from pyroute2 import NetNS

    # Create IPDB to work with the 'test' ip netns.
    #
    # Pls notice, that IPDB itself will work in the
    # main netns, only the netlink transport is
    # working in the namespace `test`.
    ip = IPDB(nl=NetNS('test'))

    # Wait until someone will set up ipaddr 127.0.0.1
    # in the netns on the loopback device
    ip.interfaces.lo.wait_ip('127.0.0.1')

    # The IPDB object must be released before exit to
    # sync all the possible changes that are in progress.
    ip.release()

The project contains several modules for different types of
netlink messages, not only RTNL.

network namespace samples
-------------------------

Network namespace manipulation::

    from pyroute2 import netns
    # create netns
    netns.create('test')
    # list
    print(netns.listnetns())
    # remove netns
    netns.remove('test')

Create **veth** interfaces pair and move to **netns**::

    from pyroute2 import IPDB

    ip = IPDB()
    # create interface pair
    ip.create(ifname='v0p0', kind='veth', peer='v0p1').commit()
    # move peer to netns
    with ip.interfaces.v0p1 as veth:
        veth.net_ns_fd = 'test'
    # don't forget to release before exit
    ip.release()

List interfaces in some **netns**::

    from pyroute2 import NetNS
    from pprint import pprint

    ns = NetNS('test')
    pprint(ns.get_links())
    ns.close()

More details and samples see in the documentation.

installation
------------

`make install` or `pip install pyroute2`

requires
--------

Python >= 2.7

The pyroute2 testing framework requires  **flake8**, **coverage**,
**nosetests**.

links
-----

* home: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://docs.pyroute2.org/
* list: https://groups.google.com/d/forum/pyroute2-dev
