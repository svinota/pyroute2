import pytest

from pyroute2.wirouting import InterfaceDoesNotExist, WiRoute, InterfaceExists

pytestmark = [pytest.mark.asyncio]
BAD_INTERFACE_NAME = "doesnotexist"


async def test_specialized_exceptions():
    async with WiRoute() as ipr:
        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link("get", ifname=BAD_INTERFACE_NAME)

        with pytest.raises(InterfaceExists):
            await ipr.link("add", ifname="lo", kind="dummy")

        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link("set", ifname=BAD_INTERFACE_NAME, mtu=1200)

        with pytest.raises(InterfaceDoesNotExist):
            await ipr.link(
                "property_add", ifname=BAD_INTERFACE_NAME, altname="new_name"
            )


async def test_interface_exist_by_name():
    async with WiRoute() as ipr:
        assert await ipr.interface_exists(ifname="lo") is True
        assert await ipr.interface_exists(ifname=BAD_INTERFACE_NAME) is False


async def test_rename_interface(tmp_link_ifname):
    async with WiRoute() as ipr:
        await ipr.link("add", ifname=tmp_link_ifname, kind="dummy")
        assert await ipr.interface_exists(ifname=tmp_link_ifname)
        new_name = tmp_link_ifname + "2"
        assert await ipr.interface_exists(ifname=new_name) is False
        await ipr.rename_interface(tmp_link_ifname, new_name)
        assert await ipr.interface_exists(ifname=new_name)
        assert await ipr.interface_exists(ifname=tmp_link_ifname) is False
        await ipr.link("del", ifname=new_name)


async def test_rename_interface_error(tmp_link_ifname):
    async with WiRoute() as ipr:
        await ipr.link("add", ifname=tmp_link_ifname, kind="dummy")
        with pytest.raises(InterfaceExists):
            await ipr.rename_interface(tmp_link_ifname, "lo")
        with pytest.raises(InterfaceDoesNotExist):
            await ipr.rename_interface(BAD_INTERFACE_NAME, BAD_INTERFACE_NAME + "2")
