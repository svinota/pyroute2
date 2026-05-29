"""ip-link part of WiRoute().

"""

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.exception import InterfaceDoesNotExist


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
