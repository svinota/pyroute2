#!/usr/bin/python

import pprint

from pyroute2.netlink.generic import nlsocket
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.rtnl import marshal_rtnl
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_LINK
from pyroute2.netlink.rtnl import RTNLGRP_NEIGH

if __name__ == "__main__":

    s = nlsocket(NETLINK_ROUTE)
    s.bind(RTNLGRP_IPV4_IFADDR | RTNLGRP_IPV6_IFADDR |
           RTNLGRP_IPV4_ROUTE | RTNLGRP_IPV6_ROUTE |
           RTNLGRP_LINK | RTNLGRP_NEIGH)
    m = marshal_rtnl(s)
    while True:
        print("-----------------------------------------------")
        pprint.pprint(m.recv())
