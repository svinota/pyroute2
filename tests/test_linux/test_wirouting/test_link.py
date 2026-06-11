import pytest

from pyroute2.wirouting import WiRoute

pytestmark = [pytest.mark.asyncio]


async def test_get_links_view(tmp_link_ifname, nsname):
    async with WiRoute(netns=nsname) as wiroute:
        await wiroute.link("add", ifname=tmp_link_ifname, kind="dummy")

        links_must_be_found = ["lo", tmp_link_ifname]
        async for link in wiroute.get_links_view():
            try:
                links_must_be_found.remove(link.nlmsg.get_attr("IFLA_IFNAME"))
            except ValueError:
                pass

        assert (
            not links_must_be_found
        )  # Verify all link name removed because found


async def test_link_name_index_mtu(tmp_link_ifname, nsname):
    async with WiRoute(netns=nsname) as wiroute:
        await wiroute.link("add", ifname=tmp_link_ifname, kind="dummy")
        await wiroute.link("set", ifname=tmp_link_ifname, mtu=1000)
        link = await wiroute.get_link_view(ifname=tmp_link_ifname)
        assert link.mtu == 1000
        assert link.mtu.cur == 1000
        await wiroute.link("set", link=link, mtu=1500)
        assert (await link.update(wiroute)).mtu == 1500
        assert link.name == tmp_link_ifname


async def test_l2(tmp_link_ifname, nsname):
    async with WiRoute(netns=nsname) as wiroute:

        # Test dummy l2 interface
        await wiroute.link("add", ifname=tmp_link_ifname, kind="dummy")
        link = await wiroute.get_link_view(ifname=tmp_link_ifname)
        assert link.is_l2()
        await wiroute.link("remove", link=link)

        # Test tun l3 interface
        await wiroute.link(
            "add", ifname=tmp_link_ifname, kind="tuntap", mode="tun"
        )
        link = await wiroute.get_link_view(ifname=tmp_link_ifname)
        assert not link.is_l2()
