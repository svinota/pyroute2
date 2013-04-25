pyroute2
========

Python network configuration library

PyRoute2 uses Netlink protocol to communicate with the Linux kernel
and get all the information about network objects -- interfaces, routes,
addresses, ARP cache entries and so on. You can also add and delete
routes and addresses.

TODO:

*nearest*

 * VLAN linkinfo data
 * bridge info: see `./net/bridge/br_netlink.c:br_fill_ifinfo()`

*further*

 * up/down link

Example usage::

    from pyroute2 import iproute
    ip = iproute()
    links = ip.get_all_links()
