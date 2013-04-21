
from socket import AF_UNSPEC
from pyroute2.netlink import netlink
from pyroute2.netlink.rtnl import marshal_rtnl
from pyroute2.netlink.generic import NETLINK_ROUTE
from pyroute2.netlink.rtmsg.rtmsg import rtmsg
from pyroute2.netlink.rtmsg.ndmsg import ndmsg
from pyroute2.netlink.rtmsg.ifinfmsg import ifinfmsg
from pyroute2.netlink.rtmsg.ifaddrmsg import ifaddrmsg
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_IFADDR
from pyroute2.netlink.rtnl import RTNLGRP_IPV4_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_IPV6_ROUTE
from pyroute2.netlink.rtnl import RTNLGRP_LINK
from pyroute2.netlink.rtnl import RTNLGRP_NEIGH
from pyroute2.netlink.rtnl import RTM_GETNEIGH
from pyroute2.netlink.rtnl import RTM_GETLINK
from pyroute2.netlink.rtnl import RTM_GETADDR
from pyroute2.netlink.rtnl import RTM_GETROUTE


class iproute(netlink):
    marshal = marshal_rtnl
    family = NETLINK_ROUTE
    groups = RTNLGRP_IPV4_IFADDR |\
        RTNLGRP_IPV6_IFADDR |\
        RTNLGRP_IPV4_ROUTE |\
        RTNLGRP_IPV6_ROUTE |\
        RTNLGRP_NEIGH |\
        RTNLGRP_LINK

    def get_all_links(self, family=AF_UNSPEC):
        msg = ifinfmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETLINK)

    def get_all_neighbors(self, family=AF_UNSPEC):
        msg = ndmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETNEIGH)

    def get_all_addr(self, family=AF_UNSPEC):
        msg = ifaddrmsg()
        msg['family'] = family
        return self.nlm_request(msg, RTM_GETADDR)

    def get_all_routes(self, family=AF_UNSPEC, table=254):
        msg = rtmsg()
        msg['family'] = family
        msg['table'] = table
        routes = self.nlm_request(msg, RTM_GETROUTE)
        return [i for i in routes if
               [k for k in i['attrs'] if k[0] == 'dst']]
