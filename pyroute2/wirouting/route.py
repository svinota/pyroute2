"""ip-route part of WiRoute()
"""

from functools import cached_property
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from socket import AF_INET

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.tools import Cacheable


class RouteView(Cacheable):

    def __init__(self, nlmsg):
        self.nlmsg = nlmsg
        self.oifname: str | None = None
        super().__init__()

    def update_link_nlmsg(self, nlmsg):
        self.oifname = nlmsg.get_attr("IFLA_IFNAME")

    async def update(self, wiroute) -> "RouteView":
        """Clear cache and update nlmsg"""
        self.clear_cache()
        self.nlmsg = (
            await wiroute.route("get", dst=str(self.dst), family=self.family)
        )[0]
        link_nlmsg = (await wiroute.link("get", index=self.oif))[0]
        self.update_link_nlmsg(link_nlmsg)
        return self

    @property
    def family(self) -> int:
        return self.nlmsg["family"]

    @property
    def table(self) -> int:
        return self.nlmsg.get_attr('RTA_TABLE')

    @property
    def rt_type(self) -> int:
        return self.nlmsg['type']

    @cached_property
    def dest(self) -> IPv4Network | IPv6Network | None:
        if (ip := self.nlmsg.get_attr("RTA_DST")) is None:
            return None
        mask = self.nlmsg["dst_len"]
        return ip_network(f"{ip}/{mask}")

    dst = dest

    @property
    def source(self) -> IPv4Address | IPv6Address | None:
        if (source := self.nlmsg.get_attr("RTA_PREFSRC")) is None:
            return None
        return ip_address(source)

    @property
    def gateway(self) -> IPv4Address | IPv6Address | None:
        if (gateway := self.nlmsg.get_attr("RTA_GATEWAY")) is None:
            return None
        return ip_address(gateway)

    @property
    def oif(self):
        return self.nlmsg.get_attr("RTA_OIF")

    @property
    def proto(self):
        return self.nlmsg["proto"]

    @property
    def priority(self):
        return self.nlmsg.get_attr("RTA_PRIORITY")

    @property
    def scope(self):
        return self.nlmsg["scope"]

    @property
    def mtu(self):
        return (
            self.nlmsg.get_attr("RTA_METRICS").get_attr("RTAX_MTU")
            if self.nlmsg.get_attr("RTA_METRICS")
            else None
        )

    def is_default_route(self):
        return self.dest is None


class WiRouteRoute(AsyncIPRoute):
    """ip-route part of WiRoute()."""

    async def get_ipv4_routes_for(self, dst: str):
        for nlmsg in await self.route("get", dst=dst, family=AF_INET):
            route = RouteView(nlmsg)
            link_nlmsg = (await self.link("get", index=route.oif))[0]
            route.update_link_nlmsg(link_nlmsg)
            yield route
