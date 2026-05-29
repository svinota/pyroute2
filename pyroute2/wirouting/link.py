"""ip-link part of WiRoute().

"""

import errno
from collections.abc import AsyncGenerator

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.exception import InterfaceDoesNotExist
from pyroute2.wirouting.sysfs import InterfaceSysfs
from pyroute2.wirouting.tools import Cacheable


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
