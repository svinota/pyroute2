pyroute2
========

Python network configuration library

PyRoute2 uses Netlink protocol to communicate with the Linux kernel
and get/set all the information kernel network objects.

todo
----

* remote: sasl authentication
* rtnl: bridge info: see `./net/bridge/br_netlink.c:br_fill_ifinfo()`
* rtnl: traffic control -- work with queue disciplines

sample
------

More samples you can read in the project documentation. Here is
just a small snippet::

    from pyroute2 import iproute
    ip = iproute()
    print ip.get_links()

The project contains several modules for different types of
netlink messages, not only RTNL.

installation
------------

`make install` or `easy_install pyroute2`

requires
--------

Python >= 2.6

changelog
---------

* 0.1.4
    * netlink: remote netlink access
    * netlink: SSL/TLS server/client auth support
    * netlink: tcp and unix transports
    * docs: started sphinx docs
* 0.1.3
    * ipdb: context manager interface
    * ipdb: [fix] correctly handle ip addr changes in transaction
    * ipdb: [fix] make up()/down() methods transactional [#1]
    * iproute: mirror packets to 0 queue
    * iproute: [fix] handle primary ip address removal response
* 0.1.2
    * initial ipdb version
    * iproute fixes
* 0.1.1
    * initial release, iproute module

links
-----

* home: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://peet.spb.ru/pyroute2/

