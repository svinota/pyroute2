""" High-level API built on top of AsyncIPRoute.

This module provides:
    * Python dataclasses for parsed objects from kernel.
      You don't need to know NLA attributes names to use it.
    * Specialized exceptions, so caller does not have to check error code
      for most commons errors.
    * Default netlink flags strict_check and ext_ack enabled
    * Python typing
"""

from pyroute2.iproute.linux import AsyncIPRoute
from pyroute2.wirouting.exception import (
    InterfaceDoesNotExist,
    exception_factory,
)


class WiRoute(AsyncIPRoute):
    def __init__(self, *args, **kwargs):
        for key in ("ext_ack", "strict_check"):
            kwargs.setdefault(key, True)
            kwargs[key] = bool(kwargs[key])
        kwargs.setdefault("exception_factory", exception_factory)
        super().__init__(*args, **kwargs)

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
