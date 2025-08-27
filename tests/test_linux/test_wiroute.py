import pytest

from pyroute2.wirouting import InterfaceDoesNotExist, WiRoute, InterfaceExists

pytestmark = [pytest.mark.asyncio]


async def test_specialized_exceptions():
    async with WiRoute() as ipr:
        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link("get", ifname="doesnotexists")

        with pytest.raises(InterfaceExists):
            await ipr.link("add", ifname="lo", kind="dummy")

        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link("set", ifname="doesnotexists", mtu=1200)

        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link(
                "property_add", ifname="doesnotexists", altname="new_name"
            )


async def test_interface_exist_by_name():
    async with WiRoute() as ipr:
        assert await ipr.interface_exists(ifname="lo") is True
        assert await ipr.interface_exists(ifname="doesnotexists") is False
