pyroute2
========

Python network configuration library

PyRoute2 uses Netlink protocol to communicate with the Linux kernel
and get all the information about network objects -- interfaces, routes,
addresses, ARP cache entries and so on. You can also add and delete
routes and addresses.

TODO:

 * VLAN linkinfo data
 * bridge info: see `./net/bridge/br_netlink.c:br_fill_ifinfo()`

Example usage::

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
