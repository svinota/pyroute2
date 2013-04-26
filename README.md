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
    links = ip.get_links()
