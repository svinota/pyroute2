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


async def test_rename_interface(tmp_link_ifname):
    async with WiRoute() as ipr:
        await ipr.link("add", ifname=tmp_link_ifname, kind="dummy")
        assert await ipr.interface_exists(ifname=tmp_link_ifname)
        new_name = tmp_link_ifname + "2"
        assert await ipr.interface_exists(ifname=new_name) is False
        await ipr.rename_interface(tmp_link_ifname, new_name)
        assert await ipr.interface_exists(ifname=new_name)
        await ipr.link("del", ifname=new_name)


async def test_rename_interface_error(tmp_link_ifname):
    async with WiRoute() as ipr:
        await ipr.link("add", ifname=tmp_link_ifname, kind="dummy")
        with pytest.raises(InterfaceExists):
            await ipr.rename_interface(tmp_link_ifname, "lo")
        with pytest.raises(InterfaceDoesNotExist):
            await ipr.rename_interface("doesnotexists", "doesnotexists2")
