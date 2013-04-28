pyroute2
========

Python network configuration library

PyRoute2 uses Netlink protocol to communicate with the Linux kernel
and get/set all the information kernel network objects.

todo
====

 * VLAN linkinfo data
 * bridge info: see `./net/bridge/br_netlink.c:br_fill_ifinfo()`
 * traffic control -- work with queue disciplines

iproute
=======

Old-style library, that provides access to rtnetlink as is. It
helps you to retrieve and change almost all the data, available
through rtnetlink.

    from pyroute2 import iproute
    ip = iproute()
        # lookup interface by name
    dev = ip.link_lookup(ifname='eth0')[0]
        # bring it down
    ip.link('set', dev, state='down')
        # change interface MAC address and rename it
    ip.link('set', dev, address='00:11:22:33:44:55', ifname='bala')
        # add primary IP address
    ip.addr('add', dev, address='10.0.0.1', mask=24)
        # add secondary IP address
    ip.addr('add', dev, address='10.0.0.2', mask=24)
        # bring it up
    ip.link('set', dev, state='up')

ipdb
====

Experimental module, that provides high-level API to network
configuration. It represents network objects as a transactional
database with commit/rollback. It is far not production ready,
so be prepared for surprises and API changes.

    from pyroute2 import ipdb
    ip = ipdb()
    ip.eth0.down()
    ip.eth0.address = '00:11:22:33:44:55'
    ip.eth0.ifname = 'bala'
    ip.eth0.ipaddr.add(('10.0.0.1', 24))
    ip.eth0.ipaddr.add(('10.0.0.2', 24))
    ip.eth0.commit()
    ip.bala.up()

Actually, the form like 'ip.eth0.address' is an eye-candy. The
ipdb objects are dictionaries, so you can write the code above
as that:

    ip['eth0'].down()
    ip['eth0']['address'] = '00:11:22:33:44:55'
    ip['eth0']['ifname'] = 'bala'
    ...


taskstats
=========

All that you should know about taskstats, is that you should not
use it. But if you have to, ok:

    import os
    from pyroute2 import taskstats
    ts = taskstats()
    ts.get_pid_stat(os.getpid())

It is not implemented normally yet, but some methods are already
usable.

installation
============

make install

requires
========

Python >= 2.6

changes
=======

 * 0.1.2
  * initial ipdb version
  * iproute fixes
 * 0.1.1
  * initial release, iproute module

links
=====

 * home: https://github.com/svinota/pyroute2
 * bugs: https://github.com/svinota/pyroute2/issues
