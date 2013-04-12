pyroute2
========

Python network configuration library

PyRoute2 uses Netlink protocol to communicate with the Linux kernel
and get all the information about network objects -- interfaces, routes,
addresses, ARP cache entries and so on. Right now the access is R/O.

TODO:

*nearest*

 * IPv6 IFLA_AF_SPEC structure
 * VLAN linkinfo data
 * bridge info: see `./net/bridge/br_netlink.c:br_fill_ifinfo()`

*further*

 * add/del addr
 * up/down link
 * add/del route

Example usage::

    from pyroute2.iproute import iproute
    ip = iproute()
    links = ip.get_all_links()
    ip.stop()
    del ip
