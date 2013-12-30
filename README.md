pyroute2
========

Python netlink library. The main goal of the project is to
implement complete NETLINK\_ROUTE family as well as several
other families (NETLINK\_NETFILTER etc.)

Current feature status see in STATUS.md

sample
------

More samples you can read in the project documentation.
Low-level interface::

    from pyroute2 import IPRoute

    # get access to the netlink socket
    ip = IPRoute()

    # print interfaces
    print ip.get_links()

    # stop working with netlink and release all sockets
    ip.release()

High-level transactional interface, IPDB::

    from pyroute2 import IPDB
    # local network settings
    ip = IPDB()
    # create bridge and add ports and addresses
    # transaction will be started with `with` statement
    # and will be committed at the end of the block
    with ip.create(kind='bridge', ifname='rhev') as i:
        i.add_port(ip.em1)
        i.add_port(ip.em2)
        i.add_ip('10.0.0.2/24')


The project contains several modules for different types of
netlink messages, not only RTNL.

installation
------------

`make install` or `pip install pyroute2`

requires
--------

Python >= 2.6

  * test reqs (optional): **python-coverage**, **python-nose**

links
-----

* home: https://github.com/svinota/pyroute2
* bugs: https://github.com/svinota/pyroute2/issues
* pypi: https://pypi.python.org/pypi/pyroute2
* docs: http://peet.spb.ru/pyroute2/
* list: https://groups.google.com/d/forum/pyroute2-dev
