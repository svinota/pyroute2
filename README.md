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
    * **nfnetlink** --- netfilter API: **ipset** (work in progress), ...
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
**IPRoute** usually doesn't rely on external utilities, but in some
cases, when the kernel doesn't provide the functionality via netlink
(like on RHEL6.5), it transparently uses also brctl and sysfs to setup
bridges and bonding interfaces.

The **IPRoute** class is a 1-to-1 RTNL mapping. There are no implicit
interface lookups and so on.

Some examples::

    from socket import AF_INET
    from pyroute2 import IPRoute
    from pyroute2 import IPRouteRequest
    from pyroute2.common import AF_MPLS

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print(ip.get_links())

    # create VETH pair
    ip.link_create(ifname='v0p0', peer='v0p1', kind='veth')

    # lookup the interface and add an address
    idx = ip.link_lookup(ifname='v0p0')[0]
    ip.addr('add',
            index=idx,
            address='10.0.0.1',
            broadcast='10.0.0.255',
            prefixlen=24)

    # create a route with metrics
    req = IPRouteRequest({'dst': '172.16.0.0/24',
                          'gateway': '10.0.0.10',
                          'metrics': {'mtu': 1400,
                                      'hoplimit': 16}})
    ip.route('add', **req)

    # create a MPLS route (requires kernel >= 4.1.4)
    # $ sudo modprobe mpls_router
    # $ sudo sysctl -w net.mpls.platform_labels=1000
    req = IPRouteRequest({'family': AF_MPLS,
                          'oif': 2,
                          'via': {'family': AF_INET,
                                  'addr': '172.16.0.10'},
                          'newdst': {'label': 0x20,
                                     'bos': 1}})
    ip.route('add', **req)
    
    # release Netlink socket
    ip.close()


High-level transactional interface, **IPDB**, a network settings DB::

    from pyroute2 import IPDB
    # local network settings
    ip = IPDB()
    # create bridge and add ports and addresses
    # transaction will be started with `with` statement
    # and will be committed at the end of the block
    try:
        with ip.create(kind='bridge', ifname='rhev') as i:
            i.add_port(ip.interfaces.em1)
            i.add_port(ip.interfaces.em2)
            i.add_ip('10.0.0.2/24')
    except Exception as e:
        print(e)
    finally:
        ip.release()

The IPDB arch allows to use it transparently with network
namespaces::

    from pyroute2 import IPDB
    from pyroute2 import NetNS

    # create IPDB to work in the 'test' ip netns
    # pls notice, that IPDB itself will work in the
    # main netns
    ip = IPDB(nl=NetNS('test'))

    # wait until someone will set up ipaddr 127.0.0.1
    # in the netns on the loopback device
    ip.interfaces.lo.wait_ip('127.0.0.1')

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

Python >= 2.6

The pyroute2 testing framework requires  **flake8**, **coverage**,
**nosetests**.

links
-----

* home: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://docs.pyroute2.org/
* list: https://groups.google.com/d/forum/pyroute2-dev
