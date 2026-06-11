"""ip-link part of WiRoute().

"""

import errno
from collections.abc import AsyncGenerator
from functools import cached_property

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.exception import InterfaceDoesNotExist, InterfaceLevel3
from pyroute2.wirouting.sysfs import InterfaceSysfs
from pyroute2.wirouting.tools import Cacheable


class InterfaceMtu(int):
    """Mtu of interface, can be used like an int or an object with
    attributes min, cur, max
    """

    def __new__(cls, min_mtu, cur_mtu, max_mtu):
        self = super().__new__(cls, cur_mtu)
        self.min = min_mtu
        self.cur = cur_mtu
        self.max = max_mtu
        return self

    def __repr__(self):
        return f"Mtu(min={self.min}, cur={self.cur}, max={self.max})"


class WiRouteLinkView(Cacheable, InterfaceSysfs):
    """Class used to interpret netlink message of IPRoute.link("get", ...)"""

    def __init__(self, nlmsg):
        self.nlmsg = nlmsg
        super().__init__()

    async def update(self, wiroute) -> "WiRouteLinkView":
        """Clear cache and update nlmsg"""
        self.clear_cache()
        self.nlmsg = (await wiroute.link("get", link=self))[0]
        return self

    @property
    def index(self) -> int:
        """Return index of link"""
        return self.nlmsg["index"]

    @property
    def name(self) -> str:
        """Return main name of link"""
        return self.nlmsg.get_attr("IFLA_IFNAME")

    @cached_property
    def mtu(self) -> InterfaceMtu:
        """Return MTU of the link"""
        return InterfaceMtu(
            min_mtu=self.nlmsg.get_attr("IFLA_MIN_MTU"),
            cur_mtu=self.nlmsg.get_attr("IFLA_MTU"),
            max_mtu=self.nlmsg.get_attr("IFLA_MAX_MTU"),
        )

    def is_l2(self):
        return self.nlmsg.get_attr("IFLA_ADDRESS") is not None

    @property
    def l2_addr(self):
        l2addr = self.nlmsg.get_attr("IFLA_ADDRESS")
        if not l2addr:
            raise InterfaceLevel3(errno.ENODEV, "Not a level2 interface")
        return l2addr

    mac_address = l2_addr


class WiRouteLink(AsyncIPRoute):
    """ip-link part of WiRoute()."""

    async def interface_exists(self, **kwargs) -> bool:
        """Check that interface exists"""
        try:
            await self.link("get", **kwargs)
            return True
        except InterfaceDoesNotExist:
            return False

    async def rename_interface(self, ifname: str, new_ifname: str) -> None:
        """Rename interface"""
        ifindex = (await self.link("get", ifname=ifname))[0]["index"]
        await self.link("set", index=ifindex, ifname=new_ifname)

    async def get_links_view(
        self, **matches
    ) -> AsyncGenerator[WiRouteLinkView]:
        """Iter links and create WiRouteLinkView on each iteration."""
        async for nlmsg in await self.get_links(match=matches):
            yield WiRouteLinkView(nlmsg)

    async def get_link_view(self, **matches) -> WiRouteLinkView:
        """Return the first link found by get_links_view()"""
        async for ip_link in self.get_links_view(**matches):
            return ip_link
        raise InterfaceDoesNotExist(errno.ENODEV, f"{matches}")

    async def link(self, *args, link: WiRouteLinkView | None = None, **kwargs):
        """Override link() method to allow WiRouteLinkView objects"""
        if link is not None:
            kwargs["index"] = link.index
        return await super().link(*args, **kwargs)
