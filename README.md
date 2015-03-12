pyroute2
========

Pyroute2 is a pure Python **netlink** and Linux **network configuration**
library. It requires only Python stdlib, no 3rd party libraries.
Later it can change, but the deps tree will remain as simple, as
it is possible.

The library provides several modules:

1. Netlink protocol implementations (RTNetlink, TaskStats, etc)

  * **rtnl**, network settings — addresses, routes, traffic controls
  * **nl80211** — wireless functions API (work in progress)
  * **nfnetlink** — netfilter API: **ipset** (work in progress), …
  * **ipq** — simplest userspace packet filtering, iptables QUEUE target
  * **taskstats** — extended process statistics

2. Simple netlink socket object, that can be used in poll/select
3. Network configuration module IPRoute provides API that in some
   way resembles ip/tc functionality
4. IPDB is an async transactional database of Linux network settings

rtnetlink sample
----------------

More samples you can read in the project documentation.

The lowest possible layer, simple socket interface. This
socket supports normal socket API and can be used in
poll/select::

    from pyroute2 import IPRSocket

    # create the socket
    ip = IPRSocket()

    # bind
    ip.bind()

    # get and parse a broadcast message
    ip.get()

    # close
    ip.close()


Low-level **IPRoute** utility -- Linux network configuration.
**IPRoute** usually doesn't rely on external utilities, but in some
cases, when the kernel doesn't provide the functionality via netlink
(like on RHEL6.5), it transparently uses also brctl and sysfs to setup
bridges and bonding interfaces::

    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print(ip.get_links())

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
