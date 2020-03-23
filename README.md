Pyroute2
========

Pyroute2 is a pure Python **netlink** library. The core requires only Python
stdlib, no 3rd party libraries. The library was started as an RTNL protocol
implementation, so the name is **pyroute2**, but now it supports many netlink
protocols. Some supported netlink families and protocols:

* **rtnl**, network settings --- addresses, routes, traffic controls
* **nfnetlink** --- netfilter API:

    * **ipset** --- IP sets
    * **nftables** --- packet filtering
    * **nfct** --- connection tracking

* **ipq** --- simplest userspace packet filtering, iptables QUEUE target
* **devlink** --- manage and monitor devlink-enabled hardware
* **generic** --- generic netlink families:

    * **ethtool** --- low-level network interface setup
    * **wireguard** --- VPN setup
    * **nl80211** --- wireless functions API (basic support)
    * **taskstats** --- extended process statistics
    * **acpi_events** --- ACPI events monitoring
    * **thermal_events** --- thermal events monitoring
    * **VFS_DQUOT** --- disk quota events monitoring

Supported systems
-----------------

Pyroute2 runs natively on Linux and emulates some limited subset
of RTNL netlink API on BSD systems on top of PF_ROUTE notifications
and standard system tools.

Other platforms are not supported.

The simplest usecase
--------------------

The objects, provided by the library, are socket objects with an
extended API. The additional functionality aims to:

* Help to open/bind netlink sockets
* Discover generic netlink protocols and multicast groups
* Construct, encode and decode netlink and PF_ROUTE messages

Maybe the simplest usecase is to monitor events. Disk quota events::

    from pyroute2 import DQuotSocket
    # DQuotSocket automatically performs discovery and binding,
    # since it has no other functionality beside of the monitoring
    with DQuotSocket() as ds:
        for message in ds.get():
            print(message)

Get notifications about network settings changes with IPRoute::

    from pyroute2 import IPRoute
    with IPRoute() as ipr:
        # With IPRoute objects you have to call bind() manually
        ipr.bind()
        for message in ipr.get():
            print(message)

RTNetlink examples
------------------

More samples you can read in the project documentation.

Low-level **IPRoute** utility --- Linux network configuration.
The **IPRoute** class is a 1-to-1 RTNL mapping. There are no implicit
interface lookups and so on.

Some examples::

    from socket import AF_INET
    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # no monitoring here -- thus no bind()

    # print interfaces
    print(ip.get_links())

    # create VETH pair and move v0p1 to netns 'test'
    ip.link('add', ifname='v0p0', peer='v0p1', kind='veth')
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

    # create SEG6 tunnel encap mode
    # Kernel >= 4.10
    ip.route('add',
             dst='2001:0:0:10::2/128',
             oif=idx,
             encap={'type': 'seg6',
                    'mode': 'encap',
                    'segs': '2000::5,2000::6'})

    # create SEG6 tunnel inline mode
    # Kernel >= 4.10
    ip.route('add',
             dst='2001:0:0:10::2/128',
             oif=idx,
             encap={'type': 'seg6',
                    'mode': 'inline',
                    'segs': ['2000::5', '2000::6']})

    # create SEG6 tunnel with ip4ip6 encapsulation
    # Kernel >= 4.14
    ip.route('add',
             dst='172.16.0.0/24',
             oif=idx,
             encap={'type': 'seg6',
                    'mode': 'encap',
                    'segs': '2000::5,2000::6'})


    # release Netlink socket
    ip.close()


The project contains several modules for different types of
netlink messages, not only RTNL.

Network namespace examples
--------------------------

Network namespace manipulation::

    from pyroute2 import netns
    # create netns
    netns.create('test')
    # list
    print(netns.listnetns())
    # remove netns
    netns.remove('test')

Create **veth** interfaces pair and move to **netns**::

    from pyroute2 import IPRoute

    with IPRoute() as ipr:

        # create interface pair
        ipr.link('add',
                 ifname='v0p0',
                 kind='veth',
                 peer='v0p1')

        # lookup the peer index
        idx = ipr.link_lookup(ifname='v0p1')[0]

        # move the peer to the 'test' netns:
        ipr.link('set',
                 index='v0p1',
                 net_ns_fd='test')

List interfaces in some **netns**::

    from pyroute2 import NetNS
    from pprint import pprint

    ns = NetNS('test')
    pprint(ns.get_links())
    ns.close()

More details and samples see in the documentation.

Installation
------------

`make install` or `pip install pyroute2`

Requirements
------------

Python >= 2.7

The pyroute2 testing and documentaion framework requirements:

* flake8
* coverage
* nosetests
* sphinx
* aafigure
* netaddr
* dtcd (optional, https://github.com/svinota/dtcd)

Optional dependencies:

* mitogen -- for distributed rtnl
* psutil -- for ss2 tool

Links
-----

* home: https://pyroute2.org/
* srcs: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://docs.pyroute2.org/
* list: https://groups.google.com/d/forum/pyroute2-dev
